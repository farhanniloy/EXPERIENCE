"""Django settings for the Along monorepo foundation."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.product import BRAND_NAME, TIME_ZONE

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


APP_ENV = os.environ.get("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
DEBUG = _env_bool("DJANGO_DEBUG", not IS_PRODUCTION)

if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured in production.")
    SECRET_KEY = "django-insecure-dev-secret-key"
if IS_PRODUCTION and (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith("django-insecure-")
):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a strong, unique production secret.")

_configured_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
_host_list = [
    host.strip()
    for host in _configured_hosts.split(",")
    if host.strip()
]
if IS_PRODUCTION and not _host_list:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be configured in production.")
ALLOWED_HOSTS = _host_list or [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "backend",
    "frontend",
    "testserver",
]
if IS_PRODUCTION and "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Wildcard hosts are not allowed in production.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "infrastructure",
    "modules.platform",
    "modules.discovery",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "along"),
            "USER": os.environ.get("POSTGRES_USER", "along"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "along"),
            "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
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
AUTHENTICATION_BACKENDS = ["modules.platform.auth.EmailBackend"]

LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@along.local")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "register": "10/hour",
        "login": "10/hour",
        "password_reset": "5/hour",
        "host_onboarding": "10/hour",
        "experience_write": "30/hour",
        "booking": "60/hour",
        "payments": "30/hour",
        "messaging": "30/hour",
        "safety": "10/hour",
        "moderation": "120/hour",
        "default": "1000/day",
    },
    "EXCEPTION_HANDLER": "modules.platform.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "modules.platform.api.CursorPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": f"{BRAND_NAME} API",
    "DESCRIPTION": "Along marketplace API, version 1.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
BOOKING_HOLD_MINUTES = int(os.environ.get("BOOKING_HOLD_MINUTES", "15"))
PAYMENTS_PROVIDER = os.environ.get(
    "PAYMENTS_PROVIDER", "sandbox" if DEBUG and APP_ENV != "production" else ""
)
PAYMENT_WEBHOOK_SECRET = os.environ.get(
    "PAYMENT_WEBHOOK_SECRET",
    "along-development-webhook-secret" if DEBUG and APP_ENV != "production" else "",
)

_trusted_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
_trusted_origin_list = [
    origin.strip()
    for origin in _trusted_origins.split(",")
    if origin.strip()
]
if IS_PRODUCTION and not _trusted_origin_list:
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS must be configured in production.")
CSRF_TRUSTED_ORIGINS = _trusted_origin_list or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://frontend:3000",
    "http://backend:8000",
]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(
    os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False
)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
if _env_bool("DJANGO_SECURE_PROXY_SSL_HEADER"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
