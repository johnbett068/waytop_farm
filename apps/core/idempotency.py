import hashlib
import uuid

from django.core.exceptions import ValidationError
from django.db import connection


def lock_idempotency_key(value):
    """Serialize one command identity before aggregate-specific row locks."""
    try:
        key = uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({"idempotency_key": "A valid UUID is required."}) from error
    if not connection.in_atomic_block:
        raise ValidationError("Idempotency locking requires an atomic transaction.")
    if connection.vendor == "postgresql":
        digest = hashlib.blake2b(key.bytes, digest_size=8).digest()
        lock_number = int.from_bytes(digest, byteorder="big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_number])
    return key
