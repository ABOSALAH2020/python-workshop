# Python Workshop

A small Flask application for practising Python concepts and exploring object detection.

## Features

- Five quiz questions covering Discord bots, Flask, machine learning, computer vision and NLP.
- Relational SQLite storage using Flask-SQLAlchemy.
- Current result, recent attempts, personal best and overall high score.
- A separate image lab using a real pretrained YOLOv4-tiny detector on the CPU.
- Annotated images, class names, confidence scores and saved detection records.
- Player-scoped image history, validated uploads and server-side quiz scoring.

## Run locally

Use Python 3.12 or newer, then:

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -r requirements.txt
# macOS/Linux: .venv/bin/python -m pip install -r requirements.txt
```

Activate the virtual environment and run:

```bash
python run_local.py
```

The application binds to http://127.0.0.1:5058. Model files are included, so runtime inference needs no network connection. Change the author name or local port in settings.json. requirements-lock.txt records the exact package versions tested on Windows; requirements.txt allows compatible installations on other platforms.

## Image lab

Upload a still JPG, PNG or WebP image, or try the included sample. The upload limit is 8 MB and 16 million pixels. The detector knows 80 COCO object classes; predictions below 35% confidence are omitted. Low confidence, missed objects and confident mistakes are possible. Blank detections are saved honestly as an empty result.

The model is pretrained, not trained by this application. OpenCV runs YOLOv4-tiny locally on the application server. See [model sources and licenses](MODEL-NOTES.md).

## Player identity and storage

A signed browser session identifies each player for 30 days with activity renewal. This is not a password-based login. Renaming a player preserves their record; switching players starts a new one. Clearing browser cookies does not restore a previous record automatically.

The private instance/ directory holds the SQLite database, signing key and processed images. It is ignored by Git. Images are re-encoded before storage and are served only to their current player.

## Tests

```bash
python -m unittest -v
```

The 16 tests cover scoring, retries, separate players, persistence, invalid forms, output escaping, real detection, image ownership, upload limits, excessive dimensions, blank detections and the sample-photo flow. Tests use temporary data and do not change user records.

## Hosting

See [PythonAnywhere setup](DEPLOY.md). Use the hosting platform's WSGI entry point, not the local Waitress launcher. HTTPS is required by the production entry point's secure session cookies.

Documentation: [Flask](https://flask.palletsprojects.com/en/stable/), [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/en/stable/), [OpenCV DNN](https://docs.opencv.org/4.x/d6/d0f/group__dnn.html).

