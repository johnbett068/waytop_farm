import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key
from apps.inventory.availability import eligible_stock_positions
from apps.inventory.models import (
    InventoryItem,
    InventoryMovement,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationConsumption,
    SourceAllocationOperation,
    StockPosition,
)
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.orders.models import Order, OrderLine

from .models import Commitment, CommitmentSupplyEvent
from .services import _base_quantity


def _require_supply_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("inventory.release")
    ):
        raise PermissionDenied("Commitment supply requires inventory.release.")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _commercial_quantity(value):
    if isinstance(value, bool):
        raise ValidationError("Supply quantity must be a positive whole Sale Unit count.")
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Supply quantity must be a positive whole Sale Unit count.") from error
    if (
        not quantity.is_finite()
        or quantity <= 0
        or quantity != quantity.to_integral_value()
        or quantity > Decimal("9223372036854775807")
    ):
        raise ValidationError("Supply quantity must be a positive whole Sale Unit count.")
    return int(quantity)


def _normalize_audit(*, correlation_id, idempotency_key, reason, source_type, source_reference):
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = lock_idempotency_key(idempotency_key)
    reason = (reason or "").strip()
    source_type = (source_type or "").strip()
    source_reference = (source_reference or "").strip()
    if not reason or not source_type or not source_reference:
        raise ValidationError("Supply reason and source reference are required.")
    return correlation_id, idempotency_key, reason, source_type, source_reference


def _fingerprint(
    *,
    commitment_id,
    commercial_quantity,
    actor,
    correlation_id,
    reason,
    source_type,
    source_reference,
):
    payload = {
        "commitment": str(commitment_id),
        "commercial_quantity": commercial_quantity,
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
        "reason": reason,
        "source_type": source_type,
        "source_reference": source_reference,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _existing_result(*, idempotency_key, fingerprint):
    event = (
        CommitmentSupplyEvent.objects.select_related("inventory_movement")
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if event is None:
        return None
    if event.request_fingerprint != fingerprint:
        raise ValidationError("Supply idempotency key was reused with different input.")
    return event


def _reject_cross_domain_idempotency_collision(idempotency_key):
    if (
        InventoryMovement.objects.filter(idempotency_key=idempotency_key).exists()
        or ReservationEvent.objects.filter(idempotency_key=idempotency_key).exists()
        or SourceAllocationOperation.objects.filter(idempotency_key=idempotency_key).exists()
    ):
        raise ValidationError("Supply idempotency key is already used by another operation.")


def _allocation_plan(*, allocations, eligible_position_ids, required_base):
    remaining = required_base
    plan = []
    for allocation in sorted(allocations, key=lambda value: (value.created_at, str(value.id))):
        if allocation.remaining_base_quantity <= 0:
            continue
        if allocation.stock_position_id not in eligible_position_ids:
            continue
        consumed = min(allocation.remaining_base_quantity, remaining)
        if consumed > 0:
            plan.append((allocation, consumed))
            remaining -= consumed
        if remaining == 0:
            break
    if remaining != 0:
        raise ValidationError("Eligible active Allocations cannot satisfy the supply quantity.")
    return tuple(plan)


@transaction.atomic
def supply_ready_commitment(
    *,
    commitment_id,
    commercial_quantity,
    actor,
    correlation_id,
    idempotency_key,
    reason,
    source_type,
    source_reference,
):
    """Atomically issue Inventory and consume one existing READY supply partition."""
    _require_supply_permission(actor)
    commitment_id = _uuid(commitment_id, "commitment_id")
    commercial_quantity = _commercial_quantity(commercial_quantity)
    (
        correlation_id,
        idempotency_key,
        reason,
        source_type,
        source_reference,
    ) = _normalize_audit(
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
    )
    fingerprint = _fingerprint(
        commitment_id=commitment_id,
        commercial_quantity=commercial_quantity,
        actor=actor,
        correlation_id=correlation_id,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
    )
    existing = _existing_result(idempotency_key=idempotency_key, fingerprint=fingerprint)
    if existing is not None:
        return existing

    try:
        preliminary = Commitment.objects.select_related("order_line").get(id=commitment_id)
    except Commitment.DoesNotExist as error:
        raise ValidationError("Supply references an unknown Commitment.") from error
    if preliminary.order_line.supply_mode != OrderLine.SupplyMode.READY:
        raise ValidationError("PRE_ORDER Commitments cannot receive physical supply.")

    # Inventory Item is the canonical lock root for every physical mutation.
    inventory_item = InventoryItem.objects.select_for_update().get(
        pk=preliminary.inventory_item_id,
        kind=InventoryItem.Kind.PRODUCT,
        supply__isnull=True,
    )
    commitment = (
        Commitment.objects.select_for_update(of=("self",))
        .select_related("order", "order_line")
        .get(fifo_sequence=preliminary.fifo_sequence)
    )
    order_line = OrderLine.objects.select_for_update().get(pk=commitment.order_line_id)
    existing = _existing_result(idempotency_key=idempotency_key, fingerprint=fingerprint)
    if existing is not None:
        return existing
    _reject_cross_domain_idempotency_collision(idempotency_key)

    if commitment.order_line.supply_mode != OrderLine.SupplyMode.READY:
        raise ValidationError("PRE_ORDER Commitments cannot receive physical supply.")
    if commitment.order.status not in (Order.Status.CONFIRMED, Order.Status.PROCESSING):
        raise ValidationError("Physical supply requires an existing CONFIRMED or PROCESSING Order.")
    if commitment.state != Commitment.State.ACTIVE or commitment.outstanding_quantity <= 0:
        raise ValidationError("Only an ACTIVE outstanding Commitment can receive supply.")
    if order_line.outstanding_quantity != commitment.outstanding_quantity:
        raise ValidationError("Order Line and Commitment outstanding quantities do not agree.")
    if commercial_quantity > commitment.outstanding_quantity:
        raise ValidationError("Supply quantity cannot exceed Commitment outstanding quantity.")

    with localcontext() as context:
        context.prec = 50
        supplied_base = _base_quantity(
            Decimal(commercial_quantity) * commitment.base_quantity_per_sale_unit
        )
    if supplied_base > commitment.outstanding_base_quantity:
        raise ValidationError("Supply base quantity cannot exceed outstanding base quantity.")

    try:
        preliminary_reservation = Reservation.objects.get(commitment_id=commitment.fifo_sequence)
    except Reservation.DoesNotExist as error:
        raise ValidationError("READY supply requires its existing Reservation.") from error
    position_ids = list(
        SourceAllocation.objects.filter(
            reservation_id=preliminary_reservation.pk,
            remaining_base_quantity__gt=0,
        ).values_list("stock_position_id", flat=True)
    )
    positions = {
        position.pk: position
        for position in StockPosition.objects.select_for_update()
        .filter(pk__in=position_ids)
        .select_related("lot", "location")
        .order_by("pk")
    }
    reservation = Reservation.objects.select_for_update().get(pk=preliminary_reservation.pk)
    allocations = list(
        SourceAllocation.objects.select_for_update()
        .filter(reservation=reservation)
        .order_by("pk")
    )

    if reservation.state != Reservation.State.ACTIVE:
        raise ValidationError("Only an ACTIVE Reservation can be consumed.")
    if supplied_base > reservation.remaining_base_quantity:
        raise ValidationError("Supply exceeds Reservation remaining quantity.")
    active_allocation_total = sum(
        (allocation.remaining_base_quantity for allocation in allocations),
        Decimal("0.000"),
    )
    if active_allocation_total != reservation.remaining_base_quantity:
        raise ValidationError("Active Allocation totals do not match Reservation remaining quantity.")

    eligible_position_ids = set(
        eligible_stock_positions(
            inventory_item=inventory_item,
            business_date=timezone.localdate(),
            location_id=commitment.order.location_id,
        )
        .filter(pk__in=position_ids)
        .values_list("pk", flat=True)
    )
    plan = _allocation_plan(
        allocations=allocations,
        eligible_position_ids=eligible_position_ids,
        required_base=supplied_base,
    )
    for allocation, quantity in plan:
        position = positions.get(allocation.stock_position_id)
        if position is None or position.on_hand_base_quantity < quantity:
            raise ValidationError("Supply ISSUE would create negative physical Inventory.")

    movement = post_inventory_movement(
        movement_type=InventoryMovement.Type.ISSUE,
        lines=tuple(
            MovementLineInput(
                item_id=inventory_item.pk,
                lot_id=positions[allocation.stock_position_id].lot_id,
                quantity=quantity,
                source_location_id=positions[allocation.stock_position_id].location_id,
            )
            for allocation, quantity in plan
        ),
        actor=actor,
        reason=reason,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
    )

    operation = SourceAllocationOperation(
        reservation=reservation,
        kind=SourceAllocationOperation.Kind.CONSUMPTION,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    operation.save(_reservation_service_write=True)
    for allocation, quantity in plan:
        allocation.consumed_base_quantity += quantity
        allocation.remaining_base_quantity -= quantity
        allocation.save(_reservation_service_write=True)

    previous_reservation_state = reservation.state
    reservation.consumed_base_quantity += supplied_base
    reservation.remaining_base_quantity -= supplied_base
    if reservation.remaining_base_quantity == 0:
        reservation.state = Reservation.State.CONSUMED
    reservation.save(_reservation_service_write=True)
    ReservationEvent(
        reservation=reservation,
        action=ReservationEvent.Action.CONSUMED,
        previous_state=previous_reservation_state,
        new_state=reservation.state,
        base_quantity=supplied_base,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    ).save(_reservation_service_write=True)

    previous_commitment_state = commitment.state
    commitment.supplied_quantity += commercial_quantity
    commitment.supplied_base_quantity += supplied_base
    commitment.outstanding_quantity -= commercial_quantity
    commitment.outstanding_base_quantity -= supplied_base
    if commitment.outstanding_quantity == 0:
        commitment.state = Commitment.State.SATISFIED

    event = CommitmentSupplyEvent(
        commitment=commitment,
        inventory_movement=movement,
        previous_state=previous_commitment_state,
        new_state=commitment.state,
        commercial_quantity=commercial_quantity,
        base_quantity=supplied_base,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    event.save(_commitment_service_write=True)
    for line_number, (allocation, quantity) in enumerate(plan, start=1):
        SourceAllocationConsumption(
            operation=operation,
            allocation=allocation,
            supply_event=event,
            line_number=line_number,
            base_quantity=quantity,
        ).save(_reservation_service_write=True)
    commitment.save(_commitment_service_write=True)
    order_line.outstanding_quantity -= commercial_quantity
    order_line.save(_supply_service_write=True)
    return event
