from .base import *
import os

environ.Env.read_env(os.path.join(BASE_DIR, ".env.prod"))

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["yourdomain.com"])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default=5432),
    }
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# In prod: only log to console (stdout, Docker best practice)
LOGGING["root"]["handlers"] = ["console", "error_console"]