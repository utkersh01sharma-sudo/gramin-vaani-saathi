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

# Dev only: the PWA shows the code on screen so the signup flow can be walked
# through end to end without an SMS provider. prod.py leaves this False.
OTP_ECHO_IN_RESPONSE = True
