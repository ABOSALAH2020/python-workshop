import os
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from questions import QUESTIONS
from vision import MAX_FILE_BYTES, ObjectDetector, read_image


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="user")


class Attempt(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    score: Mapped[int]
    total: Mapped[int]
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    user: Mapped[User] = relationship(back_populates="attempts")


class ImageAnalysis(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    filename: Mapped[str] = mapped_column(String(80))
    detections: Mapped[list] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(40), default="YOLOv4-tiny / COCO")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def create_app(test_config=None):
    app = Flask(__name__)
    instance = Path(app.instance_path)
    instance.mkdir(exist_ok=True)
    settings_file = Path(app.root_path) / "settings.json"
    settings = json.loads(settings_file.read_text(encoding="utf-8"))

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key and not test_config:
        # Keep local sessions valid after a restart without committing the key.
        key_file = instance / "session.key"
        try:
            with key_file.open("x", encoding="utf-8") as stream:
                stream.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        secret_key = key_file.read_text(encoding="utf-8").strip()

    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI="sqlite:///workshop.db",
        AUTHOR_NAME=os.environ.get("AUTHOR_NAME", settings["author_name"]),
        IMAGE_FOLDER=str(instance / "images"),
        MAX_CONTENT_LENGTH=MAX_FILE_BYTES + 64 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY before starting the application.")

    db.init_app(app)
    Path(app.config["IMAGE_FOLDER"]).mkdir(parents=True, exist_ok=True)
    detector = ObjectDetector()
    with app.app_context():
        db.create_all()

    def current_user():
        user_id = session.get("user_id")
        return db.session.get(User, user_id) if user_id else None

    @app.get("/health")
    def health():
        return {"application": "python-workshop", "status": "ok"}

    @app.before_request
    def check_form_token():
        if request.method == "POST":
            expected = session.get("form_token")
            received = request.form.get("form_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), received.encode()):
                abort(400, "The form expired. Reload the page and try again.")

    @app.context_processor
    def page_context():
        session.setdefault("form_token", secrets.token_urlsafe(24))
        user = current_user()
        global_best = db.session.scalar(db.select(func.max(Attempt.score)))
        personal_best = None
        if user:
            personal_best = db.session.scalar(
                db.select(func.max(Attempt.score)).where(Attempt.user_id == user.id)
            )
        return {
            "current_user": user,
            "global_best": global_best,
            "personal_best": personal_best,
            "question_count": len(QUESTIONS),
            "author_name": app.config["AUTHOR_NAME"],
            "form_token": session["form_token"],
        }

    @app.route("/", methods=["GET", "POST"])
    def home():
        if request.method == "POST":
            name = " ".join(request.form.get("name", "").split())
            if not 1 <= len(name) <= 40:
                flash("Use a name between 1 and 40 characters.")
                return render_template("home.html"), 400
            user = current_user()
            if user is None:
                user = User(name=name)
                db.session.add(user)
            else:
                user.name = name
            db.session.commit()
            session.permanent = True
            session["user_id"] = user.id
            return redirect(url_for("quiz"))
        return render_template("home.html")

    @app.route("/quiz", methods=["GET", "POST"])
    def quiz():
        user = current_user()
        if user is None:
            return redirect(url_for("home"))

        if request.method == "POST":
            expected = session.get("quiz_token")
            received = request.form.get("quiz_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), received.encode()):
                flash("That attempt has already been submitted or replaced. Please try again.")
                return redirect(url_for("quiz"))

            answers = {}
            for question in QUESTIONS:
                value = request.form.get(question["id"], "")
                valid_values = {str(i) for i in range(len(question["choices"]))}
                if value not in valid_values:
                    flash("Choose one answer for every question.")
                    return render_template("quiz.html", questions=QUESTIONS), 400
                answers[question["id"]] = int(value)

            # Calculate from our answer key, never from a score sent by the browser.
            score = sum(answers[q["id"]] == q["answer"] for q in QUESTIONS)
            attempt = Attempt(user=user, score=score, total=len(QUESTIONS))
            db.session.add(attempt)
            db.session.commit()
            session.pop("quiz_token", None)
            return redirect(url_for("results"))

        session["quiz_token"] = secrets.token_urlsafe(24)
        return render_template("quiz.html", questions=QUESTIONS)

    @app.get("/results")
    def results():
        user = current_user()
        if user is None:
            return redirect(url_for("home"))
        attempts = db.session.scalars(
            db.select(Attempt)
            .where(Attempt.user_id == user.id)
            .order_by(Attempt.submitted_at.desc(), Attempt.id.desc())
            .limit(10)
        ).all()
        return render_template("results.html", attempts=attempts, questions=QUESTIONS)

    def recent_images(user_id):
        return db.session.scalars(
            db.select(ImageAnalysis)
            .where(ImageAnalysis.user_id == user_id)
            .order_by(ImageAnalysis.id.desc())
            .limit(10)
        ).all()

    @app.route("/images", methods=["GET", "POST"])
    def images():
        user = current_user()
        if user is None:
            flash("Choose a player name first, then open Image lab.")
            return redirect(url_for("home"))
        if request.method == "POST":
            upload = request.files.get("image")
            use_sample = request.form.get("use_sample") == "1"
            if not use_sample and (upload is None or not upload.filename):
                flash("Choose an image to analyse.")
                return render_template("images.html", analyses=recent_images(user.id)), 400
            try:
                data = (Path(app.root_path) / "samples" / "dog.jpg").read_bytes() if use_sample else upload.read(MAX_FILE_BYTES + 1)
                image = read_image(data)
                detections, annotated = detector.detect(image)
            except ValueError as error:
                flash(str(error))
                return render_template("images.html", analyses=recent_images(user.id)), 400
            except RuntimeError as error:
                return render_template("error.html", message=str(error)), 503
            except Exception:
                app.logger.exception("Image analysis failed")
                return render_template("error.html", message="The image could not be analysed. Please try another one."), 500

            filename = secrets.token_hex(16) + ".jpg"
            saved_image = Path(app.config["IMAGE_FOLDER"]) / filename
            try:
                annotated.save(saved_image, "JPEG", quality=90)
                analysis = ImageAnalysis(user_id=user.id, filename=filename, detections=detections)
                db.session.add(analysis)
                db.session.commit()
            except (OSError, SQLAlchemyError):
                db.session.rollback()
                saved_image.unlink(missing_ok=True)
                app.logger.exception("Image result could not be saved")
                return render_template("error.html", message="The result could not be saved. Check the free space and try again."), 500
            return redirect(url_for("image_result", analysis_id=analysis.id))
        return render_template("images.html", analyses=recent_images(user.id))

    def owned_analysis(analysis_id):
        user = current_user()
        if user is None:
            abort(404)
        analysis = db.get_or_404(ImageAnalysis, analysis_id)
        if analysis.user_id != user.id:
            abort(404)
        return analysis

    @app.get("/images/<int:analysis_id>")
    def image_result(analysis_id):
        return render_template("image_result.html", analysis=owned_analysis(analysis_id))

    @app.get("/images/<int:analysis_id>/photo")
    def image_file(analysis_id):
        analysis = owned_analysis(analysis_id)
        return send_from_directory(app.config["IMAGE_FOLDER"], analysis.filename, mimetype="image/jpeg")

    @app.get("/sample-photo")
    def sample_photo():
        return send_from_directory(Path(app.root_path) / "samples", "dog.jpg", as_attachment=True)

    @app.post("/leave")
    def leave():
        session.clear()
        return redirect(url_for("home"))

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", message=error.description), 400

    @app.errorhandler(413)
    def file_too_large(error):
        return render_template("error.html", message="That upload is too large. Choose an image smaller than 8 MB."), 413

    @app.errorhandler(404)
    def page_missing(error):
        return render_template("error.html", message="This page is unavailable for the current player."), 404

    @app.errorhandler(500)
    def unexpected_error(error):
        return render_template("error.html", message="Something went wrong. Please return to the start and try again."), 500

    return app


if __name__ == "__main__":
    from waitress import serve

    settings = json.loads((Path(__file__).parent / "settings.json").read_text(encoding="utf-8"))
    print(f"Python Workshop is running at http://127.0.0.1:{settings['port']}", flush=True)
    serve(create_app(), host="127.0.0.1", port=int(settings["port"]), threads=4,
          max_request_body_size=MAX_FILE_BYTES + 128 * 1024)
