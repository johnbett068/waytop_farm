import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key

from .models import InventoryAdjustmentRequest, InventoryMovement
from .services import (
    MovementLineInput, _ADJUSTMENT_APPROVAL_TOKEN, post_inventory_movement,
)


def _require(actor, permission):
    if (
        actor is None or not actor.is_authenticated or not actor.is_active
        or not actor.is_staff or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Inventory adjustment requires {permission}.")


def _quantity(value):
    try:
        raw = Decimal(str(value))
        quantity = raw.quantize(Decimal("0.001"))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Adjustment quantity must be a valid Decimal(32,3).") from error
    if not raw.is_finite() or raw != quantity or quantity <= 0:
        raise ValidationError("Adjustment quantity must be positive and finite.")
    return quantity


def _fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@transaction.atomic
def request_inventory_adjustment(
    *, item_id, lot_id, location_id, direction, base_quantity, actor, reason,
    correlation_id, idempotency_key,
):
    _require(actor, "inventory.adjust")
    idempotency_key = lock_idempotency_key(idempotency_key)
    quantity = _quantity(base_quantity)
    payload = {
        "item": str(item_id), "lot": str(lot_id), "location": str(location_id),
        "direction": direction, "quantity": format(quantity, "f"),
        "actor": str(actor.pk), "reason": (reason or "").strip(),
        "correlation": str(correlation_id),
    }
    fingerprint = _fingerprint(payload)
    existing = InventoryAdjustmentRequest.objects.filter(
        request_idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("Adjustment request key was reused with different input.")
        return existing
    if direction not in InventoryAdjustmentRequest.Direction.values:
        raise ValidationError({"direction": "Unknown adjustment direction."})
    adjustment = InventoryAdjustmentRequest(
        item_id=item_id, lot_id=lot_id, location_id=location_id, direction=direction,
        base_quantity=quantity, requester=actor, request_reason=payload["reason"],
        correlation_id=correlation_id, request_idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    adjustment.save(_inventory_adjustment_service_write=True)
    return adjustment


@transaction.atomic
def approve_inventory_adjustment(
    *, adjustment_id, actor, reason, correlation_id, idempotency_key,
):
    _require(actor, "inventory.approve_adjustment")
    idempotency_key = lock_idempotency_key(idempotency_key)
    adjustment = InventoryAdjustmentRequest.objects.select_for_update(of=("self",)).select_related(
        "item__supply", "item__product", "lot", "location", "requester"
    ).get(pk=adjustment_id)
    payload = {
        "adjustment": str(adjustment_id), "actor": str(actor.pk),
        "reason": (reason or "").strip(), "correlation": str(correlation_id),
    }
    fingerprint = _fingerprint(payload)
    if adjustment.state == InventoryAdjustmentRequest.State.APPROVED:
        if adjustment.approval_idempotency_key != idempotency_key or adjustment.approval_fingerprint != fingerprint:
            raise ValidationError("Approved adjustment does not match this retry.")
        return adjustment
    if actor.pk == adjustment.requester_id:
        raise PermissionDenied("The adjustment requester cannot approve the same request.")
    if not payload["reason"]:
        raise ValidationError({"reason": "An adjustment approval reason is required."})
    movement_type = (
        InventoryMovement.Type.ADJUSTMENT_IN
        if adjustment.direction == InventoryAdjustmentRequest.Direction.IN
        else InventoryMovement.Type.ADJUSTMENT_OUT
    )
    endpoints = {
        "destination_location_id": adjustment.location_id
    } if adjustment.direction == InventoryAdjustmentRequest.Direction.IN else {
        "source_location_id": adjustment.location_id
    }
    movement = post_inventory_movement(
        movement_type=movement_type,
        lines=(MovementLineInput(
            item_id=adjustment.item_id, lot_id=adjustment.lot_id,
            quantity=adjustment.base_quantity, **endpoints,
        ),),
        actor=actor, reason=payload["reason"], idempotency_key=idempotency_key,
        correlation_id=correlation_id, source_type="INVENTORY_ADJUSTMENT",
        source_reference=str(adjustment.pk), adjustment_request=adjustment,
        _adjustment_approval_token=_ADJUSTMENT_APPROVAL_TOKEN,
    )
    adjustment.state = InventoryAdjustmentRequest.State.APPROVED
    adjustment.approver = actor
    adjustment.approval_reason = payload["reason"]
    adjustment.movement = movement
    adjustment.approval_idempotency_key = idempotency_key
    adjustment.approval_fingerprint = fingerprint
    adjustment.approved_at = timezone.now()
    adjustment.save(_inventory_adjustment_service_write=True)
    return adjustment
