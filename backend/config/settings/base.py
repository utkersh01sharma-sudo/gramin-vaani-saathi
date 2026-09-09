"""Shared Django settings. Environment-specific overrides live in dev.py / prod.py."""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    # local
    "apps.accounts",
    "apps.voice",
    "apps.banking",
    "apps.schemes",
    "apps.literacy",
    "apps.fraud",
    "apps.vision",
    "apps.sync",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Gramin Vaani Saathi API",
    "DESCRIPTION": (
        "Voice-first financial companion for rural communities. "
        "All banking and UPI operations are SIMULATED against a sandbox ledger. "
        "No real bank, PSP, or payment network is contacted."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------- Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 120
# When Redis is unavailable (student laptop, exam hall) tasks run inline instead
# of silently queueing forever. Flipped to False by docker-compose.
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true"
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------- AI layer
# "local"  -> models load in-process (dev / single-box demo)
# "remote" -> the same adapter interface talks HTTP to a model server (scale-out)
AI_BACKEND = os.getenv("AI_BACKEND", "local")
AI_REMOTE_URL = os.getenv("AI_REMOTE_URL", "http://localhost:9000")

ML_ARTIFACTS_DIR = Path(os.getenv("ML_ARTIFACTS_DIR", PROJECT_ROOT / "ml" / "artifacts"))

ASR_MODEL_SIZE = os.getenv("ASR_MODEL_SIZE", "small")
ASR_DEVICE = os.getenv("ASR_DEVICE", "auto")
ASR_COMPUTE_TYPE = os.getenv("ASR_COMPUTE_TYPE", "int8_float16")

INTENT_MODEL_PATH = os.getenv("INTENT_MODEL_PATH", str(ML_ARTIFACTS_DIR / "intent"))
SCAM_MODEL_PATH = os.getenv("SCAM_MODEL_PATH", str(ML_ARTIFACTS_DIR / "scam"))
NOTE_MODEL_PATH = os.getenv("NOTE_MODEL_PATH", str(ML_ARTIFACTS_DIR / "notes"))

# Below these thresholds we stop guessing and fall back to icon navigation.
ASR_MIN_CONFIDENCE = float(os.getenv("ASR_MIN_CONFIDENCE", "0.45"))
INTENT_MIN_CONFIDENCE = float(os.getenv("INTENT_MIN_CONFIDENCE", "0.55"))

# One spoken sentence is a few seconds of opus, i.e. tens of kilobytes. The cap
# is generous enough for a slow speaker and small enough that a malformed or
# hostile upload cannot fill the disk while a worker decodes it.
VOICE_MAX_UPLOAD_BYTES = int(os.getenv("VOICE_MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))

# ---------------------------------------------------------------- OTP / signup
# One-time codes for new-account verification.
#
# SCOPE: no real SMS gateway or transactional email provider is integrated in
# this project. OTP_DELIVERY="console" writes the code to the server log, and
# the email channel additionally goes through Django's console email backend.
# Everything else about the flow -- hashing at rest, expiry, single use, attempt
# limits, resend cooldown -- is real, so swapping in a provider later is one
# function in apps/accounts/otp.py.
OTP_DELIVERY = os.getenv("OTP_DELIVERY", "console")
OTP_LENGTH = int(os.getenv("OTP_LENGTH", "6"))
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "30"))
OTP_MAX_PER_HOUR = int(os.getenv("OTP_MAX_PER_HOUR", "5"))
# How long the "this destination is verified" token stays valid, i.e. how long a
# user has to finish the rest of the signup form after entering the code.
OTP_VERIFICATION_TTL_SECONDS = int(os.getenv("OTP_VERIFICATION_TTL_SECONDS", "900"))
# Echo the code in the API response so the flow is demonstrable without a
# carrier. Tied to DEBUG in dev.py; must stay False anywhere real.
OTP_ECHO_IN_RESPONSE = False

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@vaanisaathi.local")
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

SUPPORTED_LANGUAGES = ["hi", "en", "ta", "te"]
DEFAULT_LANGUAGE = "hi"

# Hard safety switch: the sandbox ledger must never be pointed at a real rail.
SANDBOX_MODE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
