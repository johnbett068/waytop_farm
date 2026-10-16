import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.idempotency import lock_idempotency_key
from .models import InventoryLocation
from .services import _require_permission


@transaction.atomic
def save_location(*, name, actor, idempotency_key, location_id=None):
    """Configure a stockholding site without changing ledger identity or policies."""
    permission = "inventory.change_inventorylocation" if location_id else "inventory.add_inventorylocation"
    _require_permission(actor, permission)
    key = lock_idempotency_key(idempotency_key)
    name = (name or "").strip()
    if not name:
        raise ValidationError({"name": "Location name is required."})
    if location_id:
        location = InventoryLocation.objects.select_for_update().get(pk=location_id)
        location.name = name
        location.save(update_fields=("name", "updated_at"))
        return location
    # Preserve the existing internal stable code. Repeated create submissions
    # resolve to the same Location rather than creating another site.
    identity = uuid.uuid5(key, "inventory-location")
    location, created = InventoryLocation.objects.get_or_create(
        pk=identity, defaults={"code": f"LOC-{identity.hex}", "name": name},
    )
    if not created and location.name != name:
        raise ValidationError("Location submission was reused with different details. Reload the form.")
    return location
