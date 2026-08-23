import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models


def _fernet():
    configured_keys = list(getattr(settings, "PAYMENT_EVIDENCE_ENCRYPTION_KEYS", ()))
    if configured_keys:
        keys = [key.encode("ascii") if isinstance(key, str) else key for key in configured_keys]
    else:
        if not getattr(
            settings, "PAYMENT_EVIDENCE_ALLOW_DEVELOPMENT_FALLBACK", False
        ):
            raise ImproperlyConfigured(
                "Production requires PAYMENT_EVIDENCE_ENCRYPTION_KEYS."
            )
        # Development/test fallback only. Production requires explicit rotatable keys.
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        keys = [base64.urlsafe_b64encode(digest)]
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            "PAYMENT_EVIDENCE_ENCRYPTION_KEYS must contain valid Fernet keys."
        ) from exc


class EncryptedTextField(models.TextField):
    """Encrypt sensitive text before database persistence and decrypt on loading."""

    prefix = "fernet$"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
        return f"{self.prefix}{token}"

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        if not value.startswith(self.prefix):
            raise ValidationError("Stored payment evidence is not encrypted.")
        try:
            return _fernet().decrypt(value[len(self.prefix):].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValidationError("Stored payment evidence could not be decrypted.") from exc
