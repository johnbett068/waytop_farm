import os

from django.core.exceptions import ImproperlyConfigured


DEVELOPMENT_SECRET_KEY = "django-insecure-waytop-farm-development-only"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name, default, *, environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value.")


def env_non_negative_int(name, default, *, environ=None):
    environ = os.environ if environ is None else environ
    raw_value = environ.get(name, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ImproperlyConfigured(f"{name} must be a non-negative integer.") from error
    if value < 0:
        raise ImproperlyConfigured(f"{name} must be a non-negative integer.")
    return value


def secret_key(*, debug, environ=None):
    environ = os.environ if environ is None else environ
    configured = environ.get("SECRET_KEY", "").strip()
    if debug:
        return configured or DEVELOPMENT_SECRET_KEY
    if (
        not configured
        or configured.startswith("django-insecure-")
        or len(configured) < 50
        or len(set(configured)) < 5
    ):
        raise ImproperlyConfigured(
            "Production requires a strong externally supplied SECRET_KEY."
        )
    return configured


def payment_evidence_encryption_keys(*, environ=None):
    environ = os.environ if environ is None else environ
    return [
        key.strip()
        for key in environ.get("PAYMENT_EVIDENCE_ENCRYPTION_KEYS", "").split(",")
        if key.strip()
    ]


def allowed_hosts(*, debug, environ=None):
    environ = os.environ if environ is None else environ
    raw_value = environ.get("ALLOWED_HOSTS")
    if raw_value is None:
        if debug:
            return ["127.0.0.1", "localhost"]
        raise ImproperlyConfigured("Production requires explicit ALLOWED_HOSTS.")
    hosts = [host.strip() for host in raw_value.split(",") if host.strip()]
    if not hosts:
        raise ImproperlyConfigured("ALLOWED_HOSTS must contain at least one hostname.")
    if not debug and "*" in hosts:
        raise ImproperlyConfigured("Production ALLOWED_HOSTS cannot contain a wildcard.")
    return hosts


def database_config(*, base_dir, environ=None):
    environ = os.environ if environ is None else environ
    backend = environ.get("WAYTOP_DATABASE_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite":
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": base_dir / "db.sqlite3",
            }
        }
    if backend != "postgresql":
        raise ImproperlyConfigured(
            "WAYTOP_DATABASE_BACKEND must be either sqlite or postgresql."
        )

    required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required if not environ.get(name, "").strip()]
    if missing:
        raise ImproperlyConfigured(
            "PostgreSQL configuration is missing: " + ", ".join(missing)
        )
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": environ["POSTGRES_DB"].strip(),
        "USER": environ["POSTGRES_USER"].strip(),
        "PASSWORD": environ["POSTGRES_PASSWORD"],
        "HOST": environ.get("POSTGRES_HOST", "127.0.0.1").strip(),
        "PORT": environ.get("POSTGRES_PORT", "5432").strip(),
        "CONN_MAX_AGE": 0,
    }
    test_name = environ.get("POSTGRES_TEST_DB", "").strip()
    if test_name:
        if test_name == config["NAME"]:
            raise ImproperlyConfigured(
                "POSTGRES_TEST_DB must differ from POSTGRES_DB."
            )
        config["TEST"] = {"NAME": test_name}
    sslmode = environ.get("POSTGRES_SSLMODE", "").strip()
    if sslmode:
        config["OPTIONS"] = {"sslmode": sslmode}
    return {"default": config}
