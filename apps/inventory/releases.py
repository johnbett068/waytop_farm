import hashlib
import json
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection

from .models import (
    InventoryItem,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationOperation,
    StockPosition,
)


def _require_cancellation_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("orders.cancel")
    ):
        raise PermissionDenied("Cancellation release requires orders.cancel.")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _fingerprint(*, reservation_id, actor, correlation_id, reason, source_reference):
    payload = {
        "reservation": str(reservation_id),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
        "reason": reason,
        "source_type": "ORDER_CANCELLATION",
        "source_reference": source_reference,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _release_ready_reservation_for_cancellation(
    *, reservation_id, actor, correlation_id, idempotency_key, reason, source_reference
):
    """Release only the remaining READY partition inside an Order cancellation transaction."""
    if not connection.in_atomic_block:
        raise ValidationError("Cancellation release requires an outer atomic transaction.")
    _require_cancellation_permission(actor)
    reservation_id = _uuid(reservation_id, "reservation_id")
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = _uuid(idempotency_key, "idempotency_key")
    reason = (reason or "").strip()
    source_reference = (source_reference or "").strip()
    if not reason or not source_reference:
        raise ValidationError("Cancellation release requires reason and Order reference.")
    fingerprint = _fingerprint(
        reservation_id=reservation_id,
        actor=actor,
        correlation_id=correlation_id,
        reason=reason,
        source_reference=source_reference,
    )
    existing = SourceAllocationOperation.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if (
            existing.reservation_id != reservation_id
            or existing.kind != SourceAllocationOperation.Kind.RELEASE
            or existing.request_fingerprint != fingerprint
        ):
            raise ValidationError("Cancellation-release idempotency key was reused with different input.")
        return existing.reservation

    preliminary = Reservation.objects.select_related("commitment__order_line").get(pk=reservation_id)
    if preliminary.commitment.order_line.supply_mode != "READY":
        raise ValidationError("Only a READY Reservation can be released by Order cancellation.")
    InventoryItem.objects.select_for_update().get(pk=preliminary.inventory_item_id)
    position_ids = sorted(
        SourceAllocation.objects.filter(reservation_id=reservation_id)
        .values_list("stock_position_id", flat=True),
        key=str,
    )
    list(StockPosition.objects.select_for_update().filter(pk__in=position_ids).order_by("pk"))
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)
    allocations = list(
        SourceAllocation.objects.select_for_update()
        .filter(reservation=reservation)
        .order_by("pk")
    )

    if reservation.state != Reservation.State.ACTIVE or reservation.remaining_base_quantity <= 0:
        raise ValidationError("Only an ACTIVE remaining Reservation can be released.")
    remaining_allocations = tuple(
        allocation for allocation in allocations if allocation.remaining_base_quantity > 0
    )
    active_total = sum(
        (allocation.remaining_base_quantity for allocation in remaining_allocations),
        Decimal("0.000"),
    )
    if active_total != reservation.remaining_base_quantity:
        raise ValidationError("Active Allocation totals do not match Reservation remaining quantity.")

    operation = SourceAllocationOperation(
        reservation=reservation,
        kind=SourceAllocationOperation.Kind.RELEASE,
        actor=actor,
        reason=reason,
        source_type="ORDER_CANCELLATION",
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    operation.save(_reservation_service_write=True)
    released_base = reservation.remaining_base_quantity
    for allocation in remaining_allocations:
        allocation.released_base_quantity += allocation.remaining_base_quantity
        allocation.remaining_base_quantity = Decimal("0.000")
        allocation.released_by_operation = operation
        allocation.save(_reservation_service_write=True)

    reservation.released_base_quantity += released_base
    reservation.remaining_base_quantity = Decimal("0.000")
    reservation.state = Reservation.State.RELEASED
    reservation.save(_reservation_service_write=True)
    ReservationEvent(
        reservation=reservation,
        action=ReservationEvent.Action.RELEASED,
        previous_state=Reservation.State.ACTIVE,
        new_state=Reservation.State.RELEASED,
        base_quantity=released_base,
        actor=actor,
        reason=reason,
        source_type="ORDER_CANCELLATION",
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=uuid.uuid5(idempotency_key, "reservation-event"),
    ).save(_reservation_service_write=True)
    return reservation
