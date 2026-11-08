import tempfile
import io
import unittest
from pathlib import Path

from app import Attempt, ImageAnalysis, User, create_app, db
from PIL import Image


class QuizTests(unittest.TestCase):
    def setUp(self):
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "only-used-in-tests",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "AUTHOR_NAME": "Test author",
            "IMAGE_FOLDER": self.files.name,
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def form_data(self, client=None):
        client = client or self.client
        with client.session_transaction() as state:
            return {
                "form_token": state["form_token"],
                "quiz_token": state.get("quiz_token", ""),
            }

    def start(self, client=None, name="First player"):
        client = client or self.client
        client.get("/")
        response = client.post(
            "/", data={**self.form_data(client), "name": name}, follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

    def submit(self, client=None, correct=True):
        client = client or self.client
        answers = (
            {"discord": "0", "flask": "2", "ai": "1", "vision": "2", "nlp": "0"}
            if correct
            else {"discord": "1", "flask": "0", "ai": "0", "vision": "0", "nlp": "1"}
        )
        return client.post(
            "/quiz", data={**self.form_data(client), **answers}, follow_redirects=True
        )

    def test_lower_retry_keeps_personal_best(self):
        self.start()
        self.assertEqual(self.submit().status_code, 200)
        self.client.get("/quiz")
        response = self.submit(correct=False)
        self.assertIn(b'big-score">0', response.data)
        self.assertIn(b'<strong>5<small>', response.data)
        with self.app.app_context():
            scores = db.session.scalars(db.select(Attempt.score).order_by(Attempt.id)).all()
            self.assertEqual(scores, [5, 0])

    def test_players_have_separate_histories_and_share_global_best(self):
        self.start()
        self.submit()
        second = self.app.test_client()
        self.start(second, "Second player")
        response = self.submit(second, correct=False)
        self.assertIn(b'Second player', response.data)
        self.assertNotIn(b'First player', response.data)
        self.assertIn(b'<strong>0<small>', response.data)
        self.assertIn(b'<strong>5<small>', response.data)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(db.select(db.func.count(User.id))), 2)
            attempts = db.session.scalars(db.select(Attempt).order_by(Attempt.id)).all()
            self.assertNotEqual(attempts[0].user_id, attempts[1].user_id)

    def test_missing_answer_does_not_create_an_attempt(self):
        self.start()
        response = self.client.post("/quiz", data=self.form_data())
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Choose one answer', response.data)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(db.select(db.func.count(Attempt.id))), 0)

    def test_client_score_is_ignored_and_same_attempt_cannot_be_saved_twice(self):
        self.start()
        data = {
            **self.form_data(),
            "discord": "1", "flask": "0", "ai": "0", "vision": "0", "nlp": "1",
            "score": "999",
        }
        self.client.post("/quiz", data=data)
        self.client.post("/quiz", data=data)
        with self.app.app_context():
            attempts = db.session.scalars(db.select(Attempt)).all()
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0].score, 0)

    def test_invalid_form_token_is_rejected(self):
        self.start()
        response = self.client.post("/quiz", data={"form_token": "غير صالح"})
        self.assertEqual(response.status_code, 400)

    def test_html_names_are_escaped(self):
        self.start(name='<script>alert(1)</script>')
        response = self.client.get("/quiz")
        self.assertNotIn(b'<script>alert(1)</script>', response.data)
        self.assertIn(b'&lt;script&gt;', response.data)

    def test_scores_survive_a_new_app_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {**self.config, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(directory).as_posix()}/saved.db"}
            first_app = create_app(config)
            client = first_app.test_client()
            self.start(client)
            self.submit(client)
            with first_app.app_context():
                db.session.remove()
                db.engine.dispose()
            second_app = create_app(config)
            with second_app.app_context():
                self.assertEqual(db.session.scalar(db.select(Attempt.score)), 5)
                db.session.remove()
                db.engine.dispose()

    def test_image_is_detected_saved_and_private_to_its_player(self):
        self.start()
        sample = Path(__file__).parent / "samples" / "dog.jpg"
        response = self.client.post(
            "/images", data={**self.form_data(), "image": (io.BytesIO(sample.read_bytes()), "../../dog.jpg")},
            content_type="multipart/form-data", follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'dog', response.data)
        with self.app.app_context():
            analysis = db.session.scalar(db.select(ImageAnalysis))
            self.assertIsNotNone(analysis)
            analysis_id = analysis.id
            self.assertIn("dog", [item["label"] for item in analysis.detections])
            self.assertTrue(all(0.35 <= item["confidence"] <= 1 for item in analysis.detections))
            self.assertEqual(Path(analysis.filename).suffix, ".jpg")
            self.assertNotIn("..", analysis.filename)
            self.assertTrue((Path(self.files.name) / analysis.filename).is_file())
        photo = self.client.get(f"/images/{analysis_id}/photo")
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.mimetype, "image/jpeg")
        photo.close()
        other = self.app.test_client()
        self.start(other, "Other player")
        self.assertEqual(other.get(f"/images/{analysis_id}").status_code, 404)
        self.assertEqual(other.get(f"/images/{analysis_id}/photo").status_code, 404)

    def test_fake_image_does_not_leave_a_database_record_or_file(self):
        self.start()
        response = self.client.post(
            "/images", data={**self.form_data(), "image": (io.BytesIO(b"not an image"), "photo.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(db.select(db.func.count(ImageAnalysis.id))), 0)
        self.assertEqual(list(Path(self.files.name).iterdir()), [])

    def test_missing_image_and_oversized_upload_are_rejected(self):
        self.start()
        self.assertEqual(self.client.post("/images", data=self.form_data()).status_code, 400)
        response = self.client.post(
            "/images", data={**self.form_data(), "image": (io.BytesIO(b"x" * (9 * 1024 * 1024)), "large.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn(b'8 MB', response.data)
        response.request.environ["wsgi.input"].close()
        response.close()

    def test_image_record_survives_a_new_app_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {**self.config, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(directory).as_posix()}/images.db"}
            first_app = create_app(config)
            client = first_app.test_client()
            self.start(client)
            sample = Path(__file__).parent / "samples" / "dog.jpg"
            client.post("/images", data={**self.form_data(client), "image": (io.BytesIO(sample.read_bytes()), "dog.jpg")}, content_type="multipart/form-data")
            with first_app.app_context():
                db.session.remove()
                db.engine.dispose()
            second_app = create_app(config)
            with second_app.app_context():
                saved = db.session.scalar(db.select(ImageAnalysis))
                self.assertIn("dog", [item["label"] for item in saved.detections])
                self.assertTrue((Path(self.files.name) / saved.filename).is_file())
                db.session.remove()
                db.engine.dispose()

    def test_excessive_pixel_dimensions_are_rejected(self):
        self.start()
        data = io.BytesIO()
        Image.new("RGB", (4100, 4100), "white").save(data, format="PNG")
        data.seek(0)
        response = self.client.post("/images", data={**self.form_data(), "image": (data, "huge.png")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_blank_image_saves_an_honest_empty_result(self):
        self.start()
        image = io.BytesIO()
        Image.new("RGB", (200, 200), "white").save(image, format="PNG")
        image.seek(0)
        response = self.client.post(
            "/images", data={**self.form_data(), "image": (image, "blank.png")},
            content_type="multipart/form-data", follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'0 objects found', response.data)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(db.select(ImageAnalysis)).detections, [])

    def test_footer_and_navigation_are_present_on_main_pages(self):
        self.start()
        for path in ("/", "/quiz", "/results", "/images", "/missing"):
            response = self.client.get(path)
            self.assertIn(b'Created by Test author', response.data)
            self.assertIn(b'Image lab', response.data)

    def test_anonymous_player_cannot_access_image_upload(self):
        self.assertEqual(self.client.get("/images").status_code, 302)

    def test_sample_button_uses_the_real_model(self):
        self.start()
        response = self.client.post("/images", data={**self.form_data(), "use_sample": "1"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'dog', response.data)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(db.select(db.func.count(ImageAnalysis.id))), 1)


if __name__ == "__main__":
    unittest.main()
