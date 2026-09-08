"""Local development settings: SQLite, permissive CORS, eager Celery."""
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
