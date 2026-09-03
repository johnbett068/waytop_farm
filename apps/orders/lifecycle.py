import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.commitments.models import Commitment, CommitmentEvent, CommitmentSupplyEvent
from apps.core.idempotency import lock_idempotency_key
from apps.inventory.models import (
    InventoryItem,
    InventoryMovement,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationOperation,
    StockPosition,
)
from apps.inventory.releases import _release_ready_reservation_for_cancellation
from apps.payments.models import Payment

from .models import Order, OrderLine, OrderStatusEvent


def _require_cancel_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("orders.cancel")
    ):
        raise PermissionDenied("Order cancellation requires orders.cancel.")


def _require_process_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("orders.process")
    ):
        raise PermissionDenied("Starting Order processing requires orders.process.")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _child_key(parent_key, label, object_id):
    return uuid.uuid5(parent_key, f"{label}:{object_id}")


def _matches_processing(event, *, order_id, actor, correlation_id, reason):
    return (
        event.order_id == order_id
        and event.previous_status == Order.Status.CONFIRMED
        and event.new_status == Order.Status.PROCESSING
        and event.actor_id == actor.pk
        and event.correlation_id == correlation_id
        and event.reason == reason
    )


def _validate_processing_supply_structure(*, order, lines, commitments, reservations, allocations):
    if not lines or len(lines) != len(commitments) or len(commitments) != len(reservations):
        raise ValidationError("Every READY Order Line requires one Commitment and Reservation.")
    line_by_id = {line.pk: line for line in lines}
    reservation_by_commitment = {
        reservation.commitment_id: reservation for reservation in reservations
    }
    allocations_by_reservation = {}
    for allocation in allocations:
        allocations_by_reservation.setdefault(allocation.reservation_id, []).append(allocation)

    for commitment in commitments:
        line = line_by_id.get(commitment.order_line_id)
        reservation = reservation_by_commitment.get(commitment.fifo_sequence)
        if line is None or reservation is None:
            raise ValidationError("READY processing supply relationships are incomplete.")
        if (
            commitment.order_id != order.pk
            or commitment.inventory_item.product_id != line.product_id
            or commitment.committed_quantity != line.quantity
            or commitment.base_quantity_per_sale_unit != line.base_quantity
            or commitment.committed_base_quantity
            != Decimal(line.quantity) * line.base_quantity
            or commitment.committed_quantity
            != commitment.supplied_quantity
            + commitment.cancelled_quantity
            + commitment.outstanding_quantity
            or commitment.committed_base_quantity
            != commitment.supplied_base_quantity
            + commitment.cancelled_base_quantity
            + commitment.outstanding_base_quantity
            or commitment.supplied_base_quantity
            != Decimal(commitment.supplied_quantity) * commitment.base_quantity_per_sale_unit
            or commitment.cancelled_base_quantity
            != Decimal(commitment.cancelled_quantity) * commitment.base_quantity_per_sale_unit
            or commitment.outstanding_base_quantity
            != Decimal(commitment.outstanding_quantity) * commitment.base_quantity_per_sale_unit
            or commitment.cancelled_quantity != 0
            or commitment.cancelled_base_quantity != 0
            or commitment.state
            != (
                Commitment.State.ACTIVE
                if commitment.outstanding_quantity > 0
                else Commitment.State.SATISFIED
            )
        ):
            raise ValidationError("Commitment quantities or state are invalid for PROCESSING.")
        if (
            line.confirmed_quantity != line.quantity
            or line.outstanding_quantity != commitment.outstanding_quantity
        ):
            raise ValidationError("Order Line and Commitment quantities do not agree.")
        if (
            reservation.inventory_item_id != commitment.inventory_item_id
            or reservation.initial_base_quantity != commitment.committed_base_quantity
            or reservation.initial_base_quantity
            != reservation.consumed_base_quantity
            + reservation.released_base_quantity
            + reservation.remaining_base_quantity
            or reservation.consumed_base_quantity != commitment.supplied_base_quantity
            or reservation.released_base_quantity != 0
            or reservation.remaining_base_quantity != commitment.outstanding_base_quantity
            or reservation.state
            != (
                Reservation.State.ACTIVE
                if reservation.remaining_base_quantity > 0
                else Reservation.State.CONSUMED
            )
        ):
            raise ValidationError("Reservation quantities or state are invalid for PROCESSING.")
        reservation_allocations = allocations_by_reservation.get(reservation.pk, [])
        if not reservation_allocations:
            raise ValidationError("READY processing requires its Allocation history.")
        for allocation in reservation_allocations:
            if (
                allocation.stock_position.item_id != reservation.inventory_item_id
                or allocation.initial_base_quantity
                != allocation.consumed_base_quantity
                + allocation.released_base_quantity
                + allocation.remaining_base_quantity
                or (allocation.remaining_base_quantity > 0 and allocation.released_by_operation_id)
            ):
                raise ValidationError("Allocation structure is invalid for PROCESSING.")
        if sum(
            (allocation.remaining_base_quantity for allocation in reservation_allocations),
            Decimal("0.000"),
        ) != reservation.remaining_base_quantity or sum(
            (allocation.consumed_base_quantity for allocation in reservation_allocations),
            Decimal("0.000"),
        ) != reservation.consumed_base_quantity:
            raise ValidationError("Allocation totals do not match the Reservation.")


@transaction.atomic
def start_order_processing(*, order_id, actor, correlation_id, idempotency_key, reason):
    """Explicitly start fulfillment work without mutating any Payment or supply fact."""
    _require_process_permission(actor)
    order_id = _uuid(order_id, "order_id")
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = lock_idempotency_key(idempotency_key)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Starting Order processing requires a non-empty reason.")

    order = Order.objects.select_for_update().get(pk=order_id)
    existing = OrderStatusEvent.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if not _matches_processing(
            existing,
            order_id=order_id,
            actor=actor,
            correlation_id=correlation_id,
            reason=reason,
        ):
            raise ValidationError("Processing idempotency key was reused with different input.")
        if order.status not in (
            Order.Status.PROCESSING,
            Order.Status.CANCELLED,
            Order.Status.FULFILLED,
        ):
            raise ValidationError("The prior PROCESSING transition result is incomplete.")
        return order
    _reject_parent_key_collision(idempotency_key)
    if order.status != Order.Status.CONFIRMED:
        raise ValidationError("Only a CONFIRMED Order can enter PROCESSING.")
    if order.payment.state != Payment.State.CONFIRMED:
        raise ValidationError("PROCESSING requires the Order's CONFIRMED Payment.")

    preliminary_lines = tuple(order.lines.order_by("line_number"))
    if any(line.supply_mode != OrderLine.SupplyMode.READY for line in preliminary_lines):
        raise ValidationError("Phase 1G PROCESSING supports READY Orders only.")
    item_ids = sorted(
        set(Commitment.objects.filter(order=order).values_list("inventory_item_id", flat=True)),
        key=str,
    )
    items = list(
        InventoryItem.objects.select_for_update(of=("self",))
        .filter(pk__in=item_ids)
        .select_related("product")
        .order_by("pk")
    )
    commitments = tuple(
        Commitment.objects.select_for_update(of=("self",))
        .filter(order=order)
        .select_related("inventory_item__product")
        .order_by("order_line__line_number")
    )
    lines = tuple(
        OrderLine.objects.select_for_update().filter(order=order).order_by("line_number")
    )
    if len(items) != len(item_ids):
        raise ValidationError("PROCESSING requires every Commitment Inventory Item.")
    position_ids = sorted(
        SourceAllocation.objects.filter(reservation__commitment__order=order)
        .values_list("stock_position_id", flat=True)
        .distinct(),
        key=str,
    )
    list(StockPosition.objects.select_for_update().filter(pk__in=position_ids).order_by("pk"))
    reservations = tuple(
        Reservation.objects.select_for_update()
        .filter(commitment__order=order)
        .order_by("pk")
    )
    allocations = tuple(
        SourceAllocation.objects.select_for_update()
        .filter(reservation__commitment__order=order)
        .select_related("stock_position")
        .order_by("pk")
    )
    _validate_processing_supply_structure(
        order=order,
        lines=lines,
        commitments=commitments,
        reservations=reservations,
        allocations=allocations,
    )

    order.status = Order.Status.PROCESSING
    order.save(_processing_service_write=True)
    OrderStatusEvent(
        order=order,
        previous_status=Order.Status.CONFIRMED,
        new_status=Order.Status.PROCESSING,
        actor=actor,
        reason=reason,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    ).save(_processing_service_write=True)
    return order


def _matches_cancellation(event, *, order_id, actor, correlation_id, reason):
    return (
        event.order_id == order_id
        and event.previous_status in (Order.Status.CONFIRMED, Order.Status.PROCESSING)
        and event.new_status == Order.Status.CANCELLED
        and event.actor_id == actor.pk
        and event.correlation_id == correlation_id
        and event.reason == reason
    )


def _validate_completed_cancellation(order):
    if order.status != Order.Status.CANCELLED or order.payment.state != Payment.State.CONFIRMED:
        raise ValidationError("The prior cancellation result is incomplete.")
    lines = tuple(order.lines.order_by("line_number"))
    commitments = tuple(order.commitments.select_related("reservation").order_by("order_line__line_number"))
    if len(lines) != len(commitments) or any(line.outstanding_quantity != 0 for line in lines):
        raise ValidationError("The prior cancellation left incomplete Order Line state.")
    for commitment in commitments:
        if commitment.outstanding_quantity != 0:
            raise ValidationError("The prior cancellation left an outstanding Commitment.")
        reservation = commitment.reservation
        if reservation.remaining_base_quantity != 0 or reservation.allocations.filter(
            remaining_base_quantity__gt=0
        ).exists():
            raise ValidationError("The prior cancellation left active READY supply.")
    return order


def _reject_parent_key_collision(idempotency_key):
    if (
        CommitmentEvent.objects.filter(idempotency_key=idempotency_key).exists()
        or CommitmentSupplyEvent.objects.filter(idempotency_key=idempotency_key).exists()
        or ReservationEvent.objects.filter(idempotency_key=idempotency_key).exists()
        or SourceAllocationOperation.objects.filter(idempotency_key=idempotency_key).exists()
        or InventoryMovement.objects.filter(idempotency_key=idempotency_key).exists()
    ):
        raise ValidationError("Cancellation idempotency key is already used by another operation.")


@transaction.atomic
def cancel_ready_order(*, order_id, actor, correlation_id, idempotency_key, reason):
    """Cancel one CONFIRMED/PROCESSING READY Order and release only remaining supply."""
    _require_cancel_permission(actor)
    order_id = _uuid(order_id, "order_id")
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = lock_idempotency_key(idempotency_key)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Order cancellation requires a non-empty reason.")

    order = Order.objects.select_for_update().get(pk=order_id)
    existing = OrderStatusEvent.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if not _matches_cancellation(
            existing,
            order_id=order_id,
            actor=actor,
            correlation_id=correlation_id,
            reason=reason,
        ):
            raise ValidationError("Cancellation idempotency key was reused with different input.")
        return _validate_completed_cancellation(order)
    _reject_parent_key_collision(idempotency_key)
    if order.status not in (Order.Status.CONFIRMED, Order.Status.PROCESSING):
        raise ValidationError("Only a CONFIRMED or PROCESSING Order can be cancelled.")
    if order.payment.state != Payment.State.CONFIRMED:
        raise ValidationError("Cancellation requires the Order's truthful CONFIRMED Payment.")

    preliminary_lines = tuple(order.lines.order_by("line_number"))
    if not preliminary_lines or any(
        line.supply_mode != OrderLine.SupplyMode.READY for line in preliminary_lines
    ):
        raise ValidationError("Phase 1G cancellation supports complete READY Orders only.")
    item_ids = sorted(
        set(
            Commitment.objects.filter(order=order).values_list("inventory_item_id", flat=True)
        ),
        key=str,
    )
    list(InventoryItem.objects.select_for_update().filter(pk__in=item_ids).order_by("pk"))
    commitments = tuple(
        Commitment.objects.select_for_update()
        .filter(order=order)
        .select_related("order_line")
        .order_by("order_line__line_number")
    )
    lines = tuple(
        OrderLine.objects.select_for_update().filter(order=order).order_by("line_number")
    )
    if len(lines) != len(commitments) or len(item_ids) == 0:
        raise ValidationError("Every READY Order Line requires exactly one Commitment.")
    position_ids = sorted(
        SourceAllocation.objects.filter(reservation__commitment__order=order)
        .values_list("stock_position_id", flat=True)
        .distinct(),
        key=str,
    )
    list(StockPosition.objects.select_for_update().filter(pk__in=position_ids).order_by("pk"))
    reservations = {
        reservation.commitment_id: reservation
        for reservation in Reservation.objects.select_for_update()
        .filter(commitment__order=order)
        .order_by("pk")
    }
    list(
        SourceAllocation.objects.select_for_update()
        .filter(reservation__commitment__order=order)
        .order_by("pk")
    )

    line_by_id = {line.pk: line for line in lines}
    for commitment in commitments:
        line = line_by_id[commitment.order_line_id]
        if line.outstanding_quantity != commitment.outstanding_quantity:
            raise ValidationError("Order Line and Commitment outstanding quantities do not agree.")
        reservation = reservations.get(commitment.fifo_sequence)
        if reservation is None:
            raise ValidationError("Every READY Commitment requires its Reservation.")
        if commitment.outstanding_quantity > 0:
            if (
                commitment.state != Commitment.State.ACTIVE
                or reservation.state != Reservation.State.ACTIVE
                or reservation.remaining_base_quantity != commitment.outstanding_base_quantity
            ):
                raise ValidationError("Outstanding Commitment and Reservation state do not agree.")
            _release_ready_reservation_for_cancellation(
                reservation_id=reservation.pk,
                actor=actor,
                correlation_id=correlation_id,
                idempotency_key=_child_key(idempotency_key, "allocation-release", line.pk),
                reason=reason,
                source_reference=order.order_number,
            )
            cancelled_quantity = commitment.outstanding_quantity
            cancelled_base = commitment.outstanding_base_quantity
            commitment.cancelled_quantity += cancelled_quantity
            commitment.cancelled_base_quantity += cancelled_base
            commitment.outstanding_quantity = 0
            commitment.outstanding_base_quantity = Decimal("0.000")
            commitment.state = Commitment.State.CANCELLED
            commitment.save(_commitment_service_write=True)
            CommitmentEvent(
                commitment=commitment,
                previous_state=Commitment.State.ACTIVE,
                new_state=Commitment.State.CANCELLED,
                commercial_quantity=cancelled_quantity,
                base_quantity=cancelled_base,
                actor=actor,
                reason=reason,
                source_type="ORDER_CANCELLATION",
                source_reference=order.order_number,
                correlation_id=correlation_id,
                idempotency_key=_child_key(idempotency_key, "commitment-cancel", line.pk),
            ).save(_commitment_service_write=True)
            line.outstanding_quantity = 0
            line.save(_cancellation_service_write=True)
        elif (
            commitment.state != Commitment.State.SATISFIED
            or reservation.state != Reservation.State.CONSUMED
            or reservation.remaining_base_quantity != 0
        ):
            raise ValidationError("Zero-outstanding READY supply must already be satisfied and consumed.")

    previous_status = order.status
    order.status = Order.Status.CANCELLED
    order.save(_cancellation_service_write=True)
    OrderStatusEvent(
        order=order,
        previous_status=previous_status,
        new_status=Order.Status.CANCELLED,
        actor=actor,
        reason=reason,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    ).save(_cancellation_service_write=True)
    return order
