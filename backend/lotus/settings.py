"""
Django settings for lotus project.

Generated by 'django-admin startproject' using Django 4.0.6.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
"""
import os
import re
import ssl
from datetime import timedelta
from pathlib import Path

import dj_database_url
import django_heroku
import posthog
import sentry_sdk
from decouple import config
from sentry_sdk.integrations.django import DjangoIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

EVENT_CACHE_FLUSH_SECONDS = config("EVENT_CACHE_FLUSH_SECONDS", default=180, cast=int)
EVENT_CACHE_FLUSH_COUNT = config("EVENT_CACHE_FLUSH_COUNT", default=1000, cast=int)
DOCKERIZED = config("DOCKERIZED", default=False, cast=bool)
ON_HEROKU = config("ON_HEROKU", default=False, cast=bool)
DEBUG = config("DEBUG", default=False, cast=bool)
PROFILER_ENABLED = config("PROFILER_ENABLED", default=False, cast=bool)
SECRET_KEY = config("SECRET_KEY", default="")
if SECRET_KEY == "":
    SECRET_KEY = os.urandom(32)
    print("SECRET_KEY not set. Defaulting to a random one.")
POSTGRES_DB_NAME = config("POSTGRES_DB_NAME", default="lotus")
POSTGRES_USER = config("POSTGRES_USER", default="lotus")
POSTGRES_PASSWORD = config("POSTGRES_PASSWORD", default="lotus")
SENTRY_DSN = config("SENTRY_DSN", default="")
SELF_HOSTED = config("SELF_HOSTED", default=False, cast=bool)
PRODUCT_ANALYTICS_OPT_IN = config("PRODUCT_ANALYTICS_OPT_IN", default=True, cast=bool)
PRODUCT_ANALYTICS_OPT_IN = True if not SELF_HOSTED else PRODUCT_ANALYTICS_OPT_IN

# Stripe required
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default=None)


if SENTRY_DSN != "":
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
        ],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True,
    )


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
API_KEY_CUSTOM_HEADER = "X-API-KEY"

posthog.project_api_key = config(
    "POSTHOG_API_KEY", default="phc_6HB6j1Hp68ESe2FpvodVwF48oisXYpot5Ymc06SbY9M"
)
posthog.host = "https://app.posthog.com"

if not PRODUCT_ANALYTICS_OPT_IN or DEBUG:
    posthog.disabled = True
POSTHOG_PERSON = hash(SECRET_KEY) if SELF_HOSTED else None

if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [
        "*uselotus.io",
    ]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "metering_billing",
    "corsheaders",
    "social_django",
    "djmoney",
    "django_extensions",
    "django_celery_beat",
    "rest_framework_api_key",
    "drf_spectacular",
    "simple_history",
    "knox",
    "anymail",
]

ANYMAIL = {
    "MAILGUN_API_KEY": os.environ.get("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": os.environ.get(
        "MAILGUN_SENDER_DOMAIN"
    ),  # your Mailgun domain, if needed
}

# if DEBUG:
if True:
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = "you@uselotus.io"
SECURITY_FROM_EMAIL = "security@uselotus.io"
SERVER_EMAIL = "you@uselotus.io"  # ditto (default from-email for Django errors)

if PROFILER_ENABLED:
    INSTALLED_APPS.append("silk")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

if PROFILER_ENABLED:
    MIDDLEWARE += ["silk.middleware.SilkyMiddleware"]
    SILKY_PYTHON_PROFILER = True


ROOT_URLCONF = "lotus.urls"

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
            "libraries": {
                "render_vite_bundle": (
                    "metering_billing.template_tags.render_vite_bundle"
                ),
            },
        },
    },
]

WSGI_APPLICATION = "lotus.wsgi.application"

AUTH_USER_MODEL = "metering_billing.User"
AUTHENTICATION_BACKENDS = ["metering_billing.auth_utils.EmailOrUsernameModelBackend"]
SOCIAL_AUTH_JSONFIELD_ENABLED = True
# SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# SESSION_COOKIE_AGE = 2 * 60 * 60  # set just 10 seconds to test
# SESSION_SAVE_EVERY_REQUEST = True

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            engine="django.db.backends.postgresql",
            conn_max_age=600,
        )
    }
    django_heroku.settings(locals(), databases=False)
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": POSTGRES_DB_NAME,
            "USER": POSTGRES_USER,
            "PASSWORD": POSTGRES_PASSWORD,
            "HOST": "db" if DOCKERIZED else "localhost",
            "PORT": 5432,
        }
    }

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# redis settings
if os.environ.get("REDIS_URL"):
    REDIS_URL = os.environ.get("REDIS_URL")
elif DOCKERIZED:
    REDIS_URL = f"redis://redis:6379"
else:
    REDIS_URL = f"redis://localhost:6379"

# Celery Settings
CELERY_BROKER_URL = f"{REDIS_URL}/1"
CELERY_RESULT_BACKEND = f"{REDIS_URL}/2"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/New_York"

if ON_HEROKU:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/3",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "REDIS_CLIENT_KWARGS": {"ssl_cert_reqs": ssl.CERT_NONE},
                "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None},
            },
        }
    }
elif DOCKERIZED:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/3",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "app_api": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

INTERNAL_IPS = ["127.0.0.1"]
if DOCKERIZED:
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]
    try:
        _, _, ips = socket.gethostbyname_ex("frontend")
        INTERNAL_IPS.extend(ips)
    except socket.gaierror:
        print(
            "tried to get frontend container ip but failed, current internal ips:",
            INTERNAL_IPS,
        )
        pass

VITE_APP_DIR = BASE_DIR / "src"

STATICFILES_DIRS = [BASE_DIR / "static", VITE_APP_DIR / "dist"]

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "static/"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]


MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "metering_billing.permissions.HasUserAPIKey",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "knox.auth.TokenAuthentication",
        # "metering_billing.permissions.KnoxTokenScheme",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "COERCE_DECIMAL_TO_STRING": False,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Lotus API",
    "DESCRIPTION": (
        "Lotus is an open-core pricing and billing engine. We enable API companies to"
        " automate and optimize their custom usage-based pricing for any metric."
    ),
    "VERSION": "0.0.1",
    "SERVE_INCLUDE_SCHEMA": False,
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "OrganizationApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-KEY",
            },
            "TokenAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
            },
        }
    },
    "SECURITY": [
        {
            "OrganizationApiKeyAuth": [],
            "TokenAuth": [],
        }
    ],
}
REST_KNOX = {
    "TOKEN_TTL": timedelta(hours=2),
    "AUTO_REFRESH": True,
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        "https://app.uselotus.io",
        "https://staging.uselotus.io",
    ]
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-api-key",
    "X-API-KEY",
]

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = ["https://app.uselotus.io"]


# Heroku
django_heroku.settings(locals())

# Vite generates files with 8 hash digits
# http://whitenoise.evans.io/en/stable/django.html#WHITENOISE_IMMUTABLE_FILE_TEST


def immutable_file_test(path, url):
    # Match filename with 12 hex digits before the extension
    # e.g. app.db8f2edc0c8a.js
    return re.match(r"^.+\.[0-9a-f]{8,12}\..+$", url)


WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test


if DEBUG:
    APP_URL = "http://localhost:8000"
else:
    APP_URL = "http://localhost:8000"
