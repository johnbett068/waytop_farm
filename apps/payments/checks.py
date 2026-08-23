from cryptography.fernet import Fernet
from django.conf import settings
from django.core.checks import Error, register


@register(deploy=True)
def payment_evidence_encryption_check(app_configs, **kwargs):
    keys = getattr(settings, "PAYMENT_EVIDENCE_ENCRYPTION_KEYS", ())
    if not keys:
        return [
            Error(
                "Production requires PAYMENT_EVIDENCE_ENCRYPTION_KEYS.",
                hint="Configure one or more comma-separated Fernet keys; first key encrypts, all decrypt.",
                id="payments.E001",
            )
        ]
    for key in keys:
        try:
            Fernet(key.encode("ascii") if isinstance(key, str) else key)
        except (TypeError, ValueError):
            return [
                Error(
                    "PAYMENT_EVIDENCE_ENCRYPTION_KEYS contains an invalid Fernet key.",
                    id="payments.E002",
                )
            ]
    return []
