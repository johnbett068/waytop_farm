import hashlib
import json
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.commitments.models import Commitment
from apps.core.idempotency import lock_idempotency_key
from apps.inventory.models import Reservation
from apps.orders.models import Order, OrderLine, OrderStatusEvent
from apps.payments.models import Payment

from .models import FulfillmentCompletion


def _require_complete_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("fulfillment.complete")
    ):
        raise PermissionDenied("Fulfillment completion requires fulfillment.complete.")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _fingerprint(*, order_id, actor, correlation_id, note, reference):
    payload = {
        "order": str(order_id),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
        "note": note,
        "reference": reference,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _matches(completion, *, order_id, actor, correlation_id, note, reference, fingerprint):
    return (
        completion.order_id == order_id
        and completion.completed_by_id == actor.pk
        and completion.correlation_id == correlation_id
        and completion.note == note
        and completion.reference == reference
        and completion.request_fingerprint == fingerprint
    )


@transaction.atomic
def complete_order_fulfillment(
    *, order_id, actor, correlation_id, idempotency_key, note="", reference=""
):
    """Record the minimal completion fact and transition PROCESSING to FULFILLED."""
    _require_complete_permission(actor)
    order_id = _uuid(order_id, "order_id")
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = lock_idempotency_key(idempotency_key)
    note = (note or "").strip()
    reference = (reference or "").strip()
    if len(reference) > 160:
        raise ValidationError("Fulfillment reference cannot exceed 160 characters.")
    fingerprint = _fingerprint(
        order_id=order_id,
        actor=actor,
        correlation_id=correlation_id,
        note=note,
        reference=reference,
    )

    order = Order.objects.select_for_update().get(pk=order_id)
    existing = FulfillmentCompletion.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if not _matches(
            existing,
            order_id=order_id,
            actor=actor,
            correlation_id=correlation_id,
            note=note,
            reference=reference,
            fingerprint=fingerprint,
        ):
            raise ValidationError("Fulfillment idempotency key was reused with different input.")
        if order.status != Order.Status.FULFILLED:
            raise ValidationError("The prior fulfillment completion result is incomplete.")
        return existing
    if OrderStatusEvent.objects.filter(idempotency_key=idempotency_key).exists():
        raise ValidationError("Fulfillment idempotency key is already used by another operation.")
    if order.status != Order.Status.PROCESSING:
        raise ValidationError("Only a PROCESSING Order can be fulfilled.")
    if order.payment.state != Payment.State.CONFIRMED:
        raise ValidationError("Fulfillment requires the Order's truthful CONFIRMED Payment.")

    commitments = tuple(
        Commitment.objects.select_for_update()
        .filter(order=order)
        .order_by("order_line__line_number")
    )
    lines = tuple(
        OrderLine.objects.select_for_update().filter(order=order).order_by("line_number")
    )
    if not lines or len(lines) != len(commitments):
        raise ValidationError("Every Order Line requires exactly one Commitment before completion.")
    if any(line.supply_mode != OrderLine.SupplyMode.READY for line in lines):
        raise ValidationError("Phase 1G fulfillment completion supports READY Orders only.")
    reservations = {
        reservation.commitment_id: reservation
        for reservation in Reservation.objects.select_for_update()
        .filter(commitment__order=order)
        .order_by("pk")
    }
    line_by_id = {line.pk: line for line in lines}
    for commitment in commitments:
        line = line_by_id[commitment.order_line_id]
        reservation = reservations.get(commitment.fifo_sequence)
        if (
            line.outstanding_quantity != 0
            or commitment.outstanding_quantity != 0
            or commitment.state != Commitment.State.SATISFIED
            or reservation is None
            or reservation.state != Reservation.State.CONSUMED
            or reservation.remaining_base_quantity != 0
            or reservation.allocations.filter(remaining_base_quantity__gt=0).exists()
        ):
            raise ValidationError("Fulfillment requires every READY quantity to be completely supplied.")

    completion = FulfillmentCompletion(
        order=order,
        completed_by=actor,
        note=note,
        reference=reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    completion.save(_fulfillment_service_write=True)
    order.status = Order.Status.FULFILLED
    order.save(_fulfillment_service_write=True)
    OrderStatusEvent(
        order=order,
        previous_status=Order.Status.PROCESSING,
        new_status=Order.Status.FULFILLED,
        actor=actor,
        reason=note or "Fulfillment completed",
        correlation_id=correlation_id,
        idempotency_key=uuid.uuid5(idempotency_key, "order-status"),
    ).save(_fulfillment_service_write=True)
    return completion
