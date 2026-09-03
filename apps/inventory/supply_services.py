import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.idempotency import lock_idempotency_key

from .models import InventoryItem, InventorySupply, InventorySupplyEvent


def _require(actor, permission):
    if (
        actor is None or not actor.is_authenticated or not actor.is_active
        or not actor.is_staff or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Inventory Supply operation requires {permission}.")


def require_supply_view(actor):
    _require(actor, "inventory.view")


def _fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@transaction.atomic
def create_inventory_supply(
    *, code, name, category, base_unit, allows_fractional_quantity, actor, reason,
    correlation_id, idempotency_key,
):
    _require(actor, "inventory.manage_supplies")
    idempotency_key = lock_idempotency_key(idempotency_key)
    values = {
        "code": (code or "").strip().upper(),
        "name": (name or "").strip(),
        "category": category,
        "base_unit": (base_unit or "").strip().lower(),
        "allows_fractional_quantity": bool(allows_fractional_quantity),
        "actor": str(actor.pk),
        "reason": (reason or "").strip(),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint(values)
    existing = InventorySupplyEvent.objects.select_related("supply").filter(
        idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("Supply idempotency key was reused with different input.")
        return existing.supply
    if not values["reason"]:
        raise ValidationError({"reason": "A Supply creation reason is required."})
    supply = InventorySupply(
        code=values["code"], name=values["name"], category=category,
        base_unit=values["base_unit"],
        allows_fractional_quantity=values["allows_fractional_quantity"],
    )
    supply.save(_inventory_supply_service_write=True)
    InventoryItem.objects.create(
        kind=InventoryItem.Kind.SUPPLY, supply=supply, product=None,
        base_unit=supply.base_unit,
    )
    InventorySupplyEvent(
        supply=supply, actor=actor, reason=values["reason"],
        correlation_id=correlation_id, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_inventory_supply_service_write=True)
    return supply


@transaction.atomic
def update_inventory_supply(
    *, supply_id, name, category, is_active, actor, reason, correlation_id, idempotency_key,
):
    _require(actor, "inventory.manage_supplies")
    idempotency_key = lock_idempotency_key(idempotency_key)
    values = {
        "supply_id": str(supply_id),
        "name": (name or "").strip(),
        "category": category,
        "is_active": bool(is_active),
        "actor": str(actor.pk),
        "reason": (reason or "").strip(),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint(values)
    existing = InventorySupplyEvent.objects.select_related("supply").filter(
        idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("Supply idempotency key was reused with different input.")
        return existing.supply
    if not values["reason"]:
        raise ValidationError({"reason": "A Supply change reason is required."})
    supply = InventorySupply.objects.select_for_update().get(pk=supply_id)
    supply.name = values["name"]
    supply.category = category
    supply.is_active = values["is_active"]
    supply.save(_inventory_supply_service_write=True)
    InventorySupplyEvent(
        supply=supply, actor=actor, reason=values["reason"],
        correlation_id=correlation_id, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_inventory_supply_service_write=True)
    return supply
