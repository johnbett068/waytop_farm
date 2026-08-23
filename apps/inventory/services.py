import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key

from .models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryMovementLine,
    StockLot,
    StockPosition,
)


BASE_QUANTITY_QUANTUM = Decimal("0.001")


@dataclass(frozen=True)
class MovementLineInput:
    item_id: uuid.UUID
    lot_id: uuid.UUID
    quantity: Decimal
    source_location_id: uuid.UUID | None = None
    destination_location_id: uuid.UUID | None = None


PERMISSION_BY_MOVEMENT_TYPE = {
    InventoryMovement.Type.RECEIPT: "inventory.receive",
    InventoryMovement.Type.ISSUE: "inventory.release",
    InventoryMovement.Type.TRANSFER: "inventory.transfer",
    InventoryMovement.Type.ADJUSTMENT_IN: "inventory.adjust",
    InventoryMovement.Type.ADJUSTMENT_OUT: "inventory.adjust",
    InventoryMovement.Type.REVERSAL: "inventory.adjust",
}


def _require_permission(actor, permission):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Inventory movement requires {permission}.")


def _quantity(value):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Inventory quantity must be a valid decimal.") from error
    if not quantity.is_finite() or quantity <= 0:
        raise ValidationError("Inventory quantity must be positive and finite.")
    integer_digits = max(quantity.adjusted() + 1, 0)
    if integer_digits > 29:
        raise ValidationError("Inventory quantity exceeds Decimal(32,3) precision.")
    try:
        quantized = quantity.quantize(BASE_QUANTITY_QUANTUM)
    except InvalidOperation as error:
        raise ValidationError("Inventory quantity exceeds Decimal(32,3) precision.") from error
    if quantity != quantized:
        raise ValidationError("Inventory quantity supports at most three decimal places.")
    return quantized


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _normalize_lines(lines):
    try:
        normalized = tuple(
            MovementLineInput(
                item_id=_uuid(line.item_id, "item_id"),
                lot_id=_uuid(line.lot_id, "lot_id"),
                quantity=_quantity(line.quantity),
                source_location_id=(
                    _uuid(line.source_location_id, "source_location_id")
                    if line.source_location_id
                    else None
                ),
                destination_location_id=(
                    _uuid(line.destination_location_id, "destination_location_id")
                    if line.destination_location_id
                    else None
                ),
            )
            for line in lines
        )
    except TypeError as error:
        raise ValidationError("Inventory movement lines must be an iterable of line inputs.") from error
    except AttributeError as error:
        raise ValidationError("Inventory movement lines are malformed.") from error
    if not normalized:
        raise ValidationError("An Inventory Movement requires at least one line.")
    return normalized


def _validate_line_shape(movement_type, line):
    source = line.source_location_id is not None
    destination = line.destination_location_id is not None
    if movement_type in {InventoryMovement.Type.RECEIPT, InventoryMovement.Type.ADJUSTMENT_IN}:
        valid = not source and destination
    elif movement_type in {InventoryMovement.Type.ISSUE, InventoryMovement.Type.ADJUSTMENT_OUT}:
        valid = source and not destination
    elif movement_type == InventoryMovement.Type.TRANSFER:
        valid = source and destination and line.source_location_id != line.destination_location_id
    else:
        valid = source or destination
    if not valid:
        raise ValidationError(f"Movement line endpoints are invalid for {movement_type}.")


def _fingerprint(
    *,
    movement_type,
    actor_id,
    reason,
    source_type,
    source_reference,
    correlation_id,
    effective_at,
    reverses,
    lines,
):
    payload = {
        "movement_type": movement_type,
        "actor": str(actor_id),
        "reason": reason,
        "source_type": source_type,
        "source_reference": source_reference,
        "correlation_id": str(correlation_id) if correlation_id is not None else None,
        "effective_at": effective_at.isoformat() if effective_at is not None else None,
        "reverses": str(reverses.pk) if reverses is not None else None,
        "lines": [
            {
                "item": str(line.item_id),
                "lot": str(line.lot_id),
                "quantity": format(line.quantity, "f"),
                "source": str(line.source_location_id) if line.source_location_id else None,
                "destination": (
                    str(line.destination_location_id) if line.destination_location_id else None
                ),
            }
            for line in lines
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic
def post_inventory_movement(
    *,
    movement_type,
    lines,
    actor,
    reason,
    idempotency_key,
    source_type="",
    source_reference="",
    correlation_id=None,
    effective_at=None,
    reverses=None,
):
    """Post an immutable movement and update affected Stock Positions atomically."""
    if movement_type not in InventoryMovement.Type.values:
        raise ValidationError("Unsupported Inventory movement type.")
    _require_permission(actor, PERMISSION_BY_MOVEMENT_TYPE[movement_type])
    if movement_type in {
        InventoryMovement.Type.ADJUSTMENT_IN,
        InventoryMovement.Type.ADJUSTMENT_OUT,
        InventoryMovement.Type.REVERSAL,
    }:
        raise ValidationError(
            "Adjustment and reversal posting remain unavailable until their approval workflow exists."
        )

    reason = (reason or "").strip()
    source_type = (source_type or "").strip()
    source_reference = (source_reference or "").strip()
    if not reason:
        raise ValidationError("Inventory movement reason is required.")
    if bool(source_type) != bool(source_reference):
        raise ValidationError("Source type and reference must be supplied together.")
    if effective_at is not None and timezone.is_naive(effective_at):
        raise ValidationError("Inventory movement effective time must be timezone-aware.")

    normalized_lines = _normalize_lines(lines)
    for line in normalized_lines:
        _validate_line_shape(movement_type, line)

    idempotency_key = lock_idempotency_key(idempotency_key)
    requested_correlation_id = (
        _uuid(correlation_id, "correlation_id") if correlation_id else None
    )
    request_fingerprint = _fingerprint(
        movement_type=movement_type,
        actor_id=actor.pk,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=requested_correlation_id,
        effective_at=effective_at,
        reverses=reverses,
        lines=normalized_lines,
    )

    existing = (
        InventoryMovement.objects.select_for_update()
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise ValidationError("Inventory idempotency key was reused with different input.")
        return existing

    item_ids = sorted({line.item_id for line in normalized_lines}, key=str)
    items = {
        item.pk: item
        for item in InventoryItem.objects.select_for_update()
        .select_related("product")
        .filter(pk__in=item_ids)
        .order_by("pk")
    }
    if set(items) != set(item_ids):
        raise ValidationError("An Inventory movement references an unknown Inventory Item.")

    # Identical commands lock the same Item pool. Recheck after that lock so a
    # concurrent retry returns the movement committed by the first transaction.
    existing = InventoryMovement.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise ValidationError("Inventory idempotency key was reused with different input.")
        return existing

    lot_ids = {line.lot_id for line in normalized_lines}
    lots = {
        lot.pk: lot
        for lot in StockLot.objects.select_for_update()
        .select_related("item")
        .filter(pk__in=lot_ids)
        .order_by("pk")
    }
    if set(lots) != lot_ids:
        raise ValidationError("An Inventory movement references an unknown Stock Lot.")

    location_ids = {
        location_id
        for line in normalized_lines
        for location_id in (line.source_location_id, line.destination_location_id)
        if location_id is not None
    }
    locations = {
        location.pk: location
        for location in InventoryLocation.objects.select_for_update()
        .filter(pk__in=location_ids)
        .order_by("pk")
    }
    if set(locations) != location_ids:
        raise ValidationError("An Inventory movement references an unknown Location.")

    for item in items.values():
        if not item.is_active:
            raise ValidationError("Inactive Inventory Items cannot receive new movements.")
        if item.base_unit != item.product.base_inventory_unit:
            raise ValidationError("Inventory Item and Product base units no longer agree.")
    if any(not lot.is_active for lot in lots.values()):
        raise ValidationError("Inactive Stock Lots cannot receive new movements.")
    if any(not location.is_active for location in locations.values()):
        raise ValidationError("Inactive Inventory Locations cannot receive new movements.")
    for line in normalized_lines:
        if lots[line.lot_id].item_id != line.item_id:
            raise ValidationError("Movement lot must belong to its Inventory Item.")

    position_keys = {
        (line.item_id, location_id, line.lot_id)
        for line in normalized_lines
        for location_id in (line.source_location_id, line.destination_location_id)
        if location_id is not None
    }
    existing_positions = (
        StockPosition.objects.select_for_update()
        .filter(item_id__in=item_ids, location_id__in=location_ids, lot_id__in=lot_ids)
        .order_by("item_id", "location_id", "lot_id")
    )
    positions = {
        (position.item_id, position.location_id, position.lot_id): position
        for position in existing_positions
        if (position.item_id, position.location_id, position.lot_id) in position_keys
    }
    deltas = {key: Decimal("0.000") for key in position_keys}
    outgoing = {key: Decimal("0.000") for key in position_keys}
    for line in normalized_lines:
        if line.source_location_id:
            source_key = (line.item_id, line.source_location_id, line.lot_id)
            outgoing[source_key] += line.quantity
            deltas[source_key] -= line.quantity
        if line.destination_location_id:
            deltas[(line.item_id, line.destination_location_id, line.lot_id)] += line.quantity

    for key, quantity in outgoing.items():
        current = positions[key].on_hand_base_quantity if key in positions else Decimal("0.000")
        if current < quantity:
            raise ValidationError("Inventory movement would create negative physical stock.")

    movement = InventoryMovement(
        movement_type=movement_type,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        correlation_id=requested_correlation_id or uuid.uuid4(),
        effective_at=effective_at or timezone.now(),
        reverses=reverses,
    )
    movement.save(_inventory_service_write=True)
    for line_number, line in enumerate(normalized_lines, start=1):
        InventoryMovementLine(
            movement=movement,
            line_number=line_number,
            item_id=line.item_id,
            lot_id=line.lot_id,
            quantity=line.quantity,
            source_location_id=line.source_location_id,
            destination_location_id=line.destination_location_id,
        ).save(_inventory_service_write=True)

    for key in sorted(position_keys, key=lambda value: tuple(map(str, value))):
        position = positions.get(key)
        if position is None:
            position = StockPosition(
                item_id=key[0],
                location_id=key[1],
                lot_id=key[2],
                on_hand_base_quantity=Decimal("0.000"),
            )
        position.on_hand_base_quantity += deltas[key]
        position.version += 1
        position.save(_inventory_service_write=True)

    return movement
