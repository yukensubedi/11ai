from .base import *
import os

# Load environment variables for dev
environ.Env.read_env(os.path.join(BASE_DIR, ".env.dev"))

DEBUG = True

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

# Add file logging in dev only
LOGGING["handlers"]["file"] = {
    "class": "logging.FileHandler",
    "filename": BASE_DIR / "logs/django.log",
    "formatter": "simple",
}
LOGGING["root"]["handlers"].append("file")