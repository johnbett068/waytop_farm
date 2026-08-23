import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from apps.commitments.models import Commitment
from apps.core.idempotency import lock_idempotency_key
from apps.orders.models import Order, OrderLine

from .availability import eligible_stock_positions
from .models import (
    InventoryItem,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationOperation,
    StockPosition,
)


BASE_QUANTITY_QUANTUM = Decimal("0.001")


@dataclass(frozen=True)
class AllocationSourceInput:
    stock_position_id: uuid.UUID
    base_quantity: Decimal


def _require_allocate_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("commitments.allocate")
    ):
        raise PermissionDenied("Source allocation requires commitments.allocate.")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _quantity(value):
    try:
        quantity = Decimal(str(value))
        quantized = quantity.quantize(BASE_QUANTITY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Allocation quantity must be a valid Decimal(32,3).") from error
    if not quantity.is_finite() or quantity <= 0 or quantity != quantized:
        raise ValidationError("Allocation quantity must be positive and exact to three decimals.")
    if max(quantity.adjusted() + 1, 0) > 29:
        raise ValidationError("Allocation quantity exceeds Decimal(32,3) precision.")
    return quantized


def _normalize_sources(sources):
    if sources is None:
        return None
    normalized = tuple(
        AllocationSourceInput(
            stock_position_id=_uuid(source.stock_position_id, "stock_position_id"),
            base_quantity=_quantity(source.base_quantity),
        )
        for source in sources
    )
    if not normalized:
        raise ValidationError("An approved source split cannot be empty.")
    ids = [source.stock_position_id for source in normalized]
    if len(ids) != len(set(ids)):
        raise ValidationError("An approved source split cannot repeat a Stock Position.")
    return tuple(sorted(normalized, key=lambda source: str(source.stock_position_id)))


def _fingerprint(
    *,
    target_id,
    actor,
    correlation_id,
    reason,
    source_type,
    source_reference,
    approved_sources,
):
    payload = {
        "target": str(target_id),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
        "reason": reason,
        "source_type": source_type,
        "source_reference": source_reference,
        "sources": (
            "AUTO"
            if approved_sources is None
            else [
                {
                    "position": str(source.stock_position_id),
                    "quantity": format(source.base_quantity, "f"),
                }
                for source in approved_sources
            ]
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _normalize_audit(*, correlation_id, idempotency_key, reason, source_type, source_reference):
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = lock_idempotency_key(idempotency_key)
    reason = (reason or "").strip()
    source_type = (source_type or "").strip()
    source_reference = (source_reference or "").strip()
    if not reason or not source_type or not source_reference:
        raise ValidationError("Reservation/allocation reason and source reference are required.")
    return correlation_id, idempotency_key, reason, source_type, source_reference


def _source_order(position):
    expiry = position.lot.expiry_date
    return (
        expiry is None,
        expiry or date.max,
        position.lot.created_at,
        position.location.code,
        str(position.pk),
    )


def _select_sources(*, positions, available_by_position, required, approved_sources):
    position_map = {position.pk: position for position in positions}
    if approved_sources is not None:
        selected = []
        total = Decimal("0.000")
        for source in approved_sources:
            position = position_map.get(source.stock_position_id)
            if position is None:
                raise ValidationError("Approved allocation source is not eligible READY stock.")
            if source.base_quantity > available_by_position.get(position.pk, Decimal("0.000")):
                raise ValidationError("Approved allocation exceeds unallocated Position stock.")
            selected.append((position, source.base_quantity))
            total += source.base_quantity
        if total != required:
            raise ValidationError("Approved allocation must completely equal the Reservation quantity.")
        return tuple(sorted(selected, key=lambda value: _source_order(value[0])))

    remaining = required
    selected = []
    for position in sorted(positions, key=_source_order):
        available = available_by_position.get(position.pk, Decimal("0.000"))
        if available <= 0:
            continue
        quantity = min(available, remaining)
        if quantity > 0:
            selected.append((position, quantity))
            remaining -= quantity
        if remaining == 0:
            break
    if remaining != 0:
        raise ValidationError("Eligible unallocated stock cannot completely satisfy the Reservation.")
    return tuple(selected)


def _locked_supply_pool(inventory_item):
    business_date = timezone.localdate()
    positions = list(
        eligible_stock_positions(
            inventory_item=inventory_item,
            business_date=business_date,
        )
        .select_for_update()
        .select_related("lot", "location")
        .order_by("pk")
    )
    reservations = list(
        Reservation.objects.select_for_update()
        .filter(inventory_item=inventory_item)
        .order_by("pk")
    )
    allocations = list(
        SourceAllocation.objects.select_for_update()
        .filter(reservation__inventory_item=inventory_item)
        .select_related("reservation", "stock_position")
        .order_by("pk")
    )
    return positions, reservations, allocations


def _available_by_position(*, positions, allocations, excluded_reservation=None):
    allocated = {}
    for allocation in allocations:
        if allocation.remaining_base_quantity <= 0:
            continue
        if excluded_reservation is not None and allocation.reservation_id == excluded_reservation.pk:
            continue
        allocated[allocation.stock_position_id] = (
            allocated.get(allocation.stock_position_id, Decimal("0.000"))
            + allocation.remaining_base_quantity
        )
    return {
        position.pk: position.on_hand_base_quantity
        - allocated.get(position.pk, Decimal("0.000"))
        for position in positions
    }


def _create_allocation_lines(*, operation, reservation, selected):
    allocations = []
    for line_number, (position, quantity) in enumerate(selected, start=1):
        allocation = SourceAllocation(
            reservation=reservation,
            operation=operation,
            stock_position=position,
            line_number=line_number,
            initial_base_quantity=quantity,
            remaining_base_quantity=quantity,
        )
        allocation.save(_reservation_service_write=True)
        allocations.append(allocation)
    return tuple(allocations)


def _existing_initial_result(*, idempotency_key, fingerprint):
    reservation = Reservation.objects.filter(
        creation_idempotency_key=idempotency_key
    ).first()
    if reservation is None:
        return None
    operation = SourceAllocationOperation.objects.filter(
        idempotency_key=idempotency_key,
        kind=SourceAllocationOperation.Kind.INITIAL,
    ).first()
    if operation is None or operation.request_fingerprint != fingerprint:
        raise ValidationError("Reservation idempotency key was reused with different input.")
    return reservation, tuple(operation.allocations.order_by("line_number"))


def reserve_and_allocate_ready_commitment(
    *,
    commitment_id,
    actor,
    correlation_id,
    idempotency_key,
    reason,
    source_type,
    source_reference,
    approved_sources=None,
    _confirmation_order_locked=False,
):
    """Internal atomic-composition boundary; caller owns the outer transaction."""
    if not connection.in_atomic_block:
        raise ValidationError("Reservation/allocation requires an outer atomic transaction.")
    _require_allocate_permission(actor)
    commitment_id = _uuid(commitment_id, "commitment_id")
    approved_sources = _normalize_sources(approved_sources)
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
        target_id=commitment_id,
        actor=actor,
        correlation_id=correlation_id,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        approved_sources=approved_sources,
    )
    existing = _existing_initial_result(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing

    try:
        commitment = Commitment.objects.select_related(
            "order", "order_line", "inventory_item"
        ).get(id=commitment_id)
    except Commitment.DoesNotExist as error:
        raise ValidationError("Reservation references an unknown Commitment.") from error
    if commitment.order_line.supply_mode != OrderLine.SupplyMode.READY:
        raise ValidationError("PRE_ORDER Commitments cannot reserve physical Inventory.")
    if commitment.order.status == Order.Status.PENDING and not _confirmation_order_locked:
        raise ValidationError("PENDING Orders cannot create Reservations.")
    if (
        commitment.state != Commitment.State.ACTIVE
        or commitment.supplied_base_quantity != 0
        or commitment.cancelled_base_quantity != 0
        or commitment.outstanding_base_quantity != commitment.committed_base_quantity
    ):
        raise ValidationError("Only a new fully outstanding ACTIVE Commitment can be reserved.")

    inventory_item = InventoryItem.objects.select_for_update().get(
        pk=commitment.inventory_item_id
    )
    fifo_pool_query = Commitment.objects.select_for_update().filter(
            inventory_item=inventory_item,
            order_line__supply_mode=OrderLine.SupplyMode.READY,
            state=Commitment.State.ACTIVE,
        )
    if _confirmation_order_locked:
        fifo_pool_query = fifo_pool_query.filter(
            Q(order__status__in=(Order.Status.CONFIRMED, Order.Status.PROCESSING))
            | Q(pk=commitment.pk)
        )
    else:
        fifo_pool_query = fifo_pool_query.filter(
            order__status__in=(Order.Status.CONFIRMED, Order.Status.PROCESSING)
        )
    fifo_pool = list(
        fifo_pool_query
        .order_by("confirmed_at", "fifo_sequence")
    )
    positions, reservations, allocations = _locked_supply_pool(inventory_item)

    existing = _existing_initial_result(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    if any(reservation.commitment_id == commitment.pk for reservation in reservations):
        raise ValidationError("This Commitment already has a Reservation.")
    reserved_commitment_ids = {reservation.commitment_id for reservation in reservations}
    for queued in fifo_pool:
        if queued.fifo_sequence == commitment.fifo_sequence:
            break
        if queued.fifo_sequence not in reserved_commitment_ids:
            raise ValidationError("An earlier eligible READY Commitment must be reserved first.")

    eligible_total = sum(
        (position.on_hand_base_quantity for position in positions),
        Decimal("0.000"),
    )
    active_reserved = sum(
        (
            reservation.remaining_base_quantity
            for reservation in reservations
            if reservation.state == Reservation.State.ACTIVE
        ),
        Decimal("0.000"),
    )
    required = commitment.committed_base_quantity
    if active_reserved + required > eligible_total:
        raise ValidationError("Eligible physical Inventory cannot satisfy this Reservation.")

    available_by_position = _available_by_position(
        positions=positions,
        allocations=allocations,
    )
    selected = _select_sources(
        positions=positions,
        available_by_position=available_by_position,
        required=required,
        approved_sources=approved_sources,
    )

    reservation = Reservation(
        commitment=commitment,
        inventory_item=inventory_item,
        initial_base_quantity=required,
        remaining_base_quantity=required,
        creation_correlation_id=correlation_id,
        creation_idempotency_key=idempotency_key,
    )
    reservation.save(
        _reservation_service_write=True,
        _confirmation_order_locked=_confirmation_order_locked,
    )
    ReservationEvent(
        reservation=reservation,
        action=ReservationEvent.Action.CREATED,
        previous_state=None,
        new_state=Reservation.State.ACTIVE,
        base_quantity=required,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    ).save(_reservation_service_write=True)
    operation = SourceAllocationOperation(
        reservation=reservation,
        kind=SourceAllocationOperation.Kind.INITIAL,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    operation.save(_reservation_service_write=True)
    created_allocations = _create_allocation_lines(
        operation=operation,
        reservation=reservation,
        selected=selected,
    )
    return reservation, created_allocations


def reallocate_ready_reservation(
    *,
    reservation_id,
    actor,
    correlation_id,
    idempotency_key,
    reason,
    source_type,
    source_reference,
    approved_sources=None,
):
    """Replace the complete remaining source split while preserving old lines."""
    if not connection.in_atomic_block:
        raise ValidationError("Reallocation requires an outer atomic transaction.")
    _require_allocate_permission(actor)
    reservation_id = _uuid(reservation_id, "reservation_id")
    approved_sources = _normalize_sources(approved_sources)
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
        target_id=reservation_id,
        actor=actor,
        correlation_id=correlation_id,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        approved_sources=approved_sources,
    )
    existing = SourceAllocationOperation.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        if (
            existing.kind != SourceAllocationOperation.Kind.REALLOCATION
            or existing.reservation_id != reservation_id
            or existing.request_fingerprint != fingerprint
        ):
            raise ValidationError("Reallocation idempotency key was reused with different input.")
        return tuple(existing.allocations.order_by("line_number"))

    try:
        preliminary = Reservation.objects.select_related("inventory_item").get(pk=reservation_id)
    except Reservation.DoesNotExist as error:
        raise ValidationError("Reallocation references an unknown Reservation.") from error
    inventory_item = InventoryItem.objects.select_for_update().get(
        pk=preliminary.inventory_item_id
    )
    positions, reservations, allocations = _locked_supply_pool(inventory_item)
    reservation = next(
        (candidate for candidate in reservations if candidate.pk == reservation_id),
        None,
    )
    if reservation is None or reservation.state != Reservation.State.ACTIVE:
        raise ValidationError("Only an ACTIVE Reservation can be reallocated.")

    existing = SourceAllocationOperation.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        if (
            existing.kind != SourceAllocationOperation.Kind.REALLOCATION
            or existing.reservation_id != reservation_id
            or existing.request_fingerprint != fingerprint
        ):
            raise ValidationError("Reallocation idempotency key was reused with different input.")
        return tuple(existing.allocations.order_by("line_number"))

    current = tuple(
        allocation
        for allocation in allocations
        if allocation.reservation_id == reservation.pk
        and allocation.remaining_base_quantity > 0
    )
    if sum(
        (allocation.remaining_base_quantity for allocation in current),
        Decimal("0.000"),
    ) != reservation.remaining_base_quantity:
        raise ValidationError("Active Allocation totals do not match the Reservation remaining quantity.")
    available_by_position = _available_by_position(
        positions=positions,
        allocations=allocations,
        excluded_reservation=reservation,
    )
    selected = _select_sources(
        positions=positions,
        available_by_position=available_by_position,
        required=reservation.remaining_base_quantity,
        approved_sources=approved_sources,
    )
    operation = SourceAllocationOperation(
        reservation=reservation,
        kind=SourceAllocationOperation.Kind.REALLOCATION,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    operation.save(_reservation_service_write=True)
    for allocation in current:
        released = allocation.remaining_base_quantity
        allocation.released_base_quantity += released
        allocation.remaining_base_quantity = Decimal("0.000")
        allocation.released_by_operation = operation
        allocation.save(_reservation_service_write=True)
    return _create_allocation_lines(
        operation=operation,
        reservation=reservation,
        selected=selected,
    )
