"""Settings SOLO para ejecutar la suite de tests.

La BD de producción es SQL Server remoto (no podemos crear una BD de test ahí),
así que se usa sqlite en memoria. Hereda todo lo demás de core.settings.

Uso:
    python manage.py test bienes --settings=core.test_settings
"""
from core.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Acelera la creación de usuarios/fixtures en tests (irrelevante en producción).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
