import os

from app import create_app


os.environ.setdefault("COOKIE_SECURE", "1")
application = create_app()
