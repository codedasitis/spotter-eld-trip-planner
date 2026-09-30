"""
Django settings for the Spotter AI ELD trip planner backend.

Security posture (see README for the full checklist):
  - SECRET_KEY, DEBUG, ALLOWED_HOSTS, CORS origins all come from the
    environment via python-decouple. The defaults below are safe for a
    cold local clone and are NOT what runs in production (Render sets
    real environment variables).
  - DEBUG defaults to False. You must opt into it locally via .env.
  - No CORS_ALLOW_ALL_ORIGINS anywhere in this file, ever.
"""

from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: 'insecure-dev-key-change-in-production' is a local-dev
# placeholder only. Render (or any real deployment) must set a real
# SECRET_KEY via environment variable -- this default is intentionally
# obviously fake so nobody mistakes it for a real secret.
SECRET_KEY = config("SECRET_KEY", default="insecure-dev-key-change-in-production")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "spotter.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "spotter.wsgi.application"

# No app models exist (see trips/models.py) -- SQLite is configured only
# because Django's admin/auth/sessions apps expect *some* database to be
# reachable at startup. The trip-planning request path never touches it.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = False  # the HOS engine works in naive local time throughout

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# CORS: locked to the Vite dev server by default. Production sets
# CORS_ALLOWED_ORIGINS to the real deployed frontend origin (e.g. the
# Vercel URL) via environment variable -- never via a code change.
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS", default="http://localhost:5173", cast=Csv()
)

# Production hardening. Deliberately NOT tied to `not DEBUG` -- coupling
# SECURE_SSL_REDIRECT to DEBUG breaks Django's test client (it doesn't
# mark requests as secure, so every response becomes a 301 instead of the
# expected status code, and every status-code assertion in the suite
# fails). These are separate, explicit opt-ins Render sets via real
# environment variables once TLS is confirmed to be in front of the app.
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
