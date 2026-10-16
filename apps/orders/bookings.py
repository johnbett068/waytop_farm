"""Cancellation releases future demand, never current inventory."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.commitments.models import Commitment, CommitmentEvent
from apps.core.idempotency import lock_idempotency_key
from apps.production.models import ProductionBatch
from .lifecycle import _require_cancel_permission, _uuid, _child_key
from .models import Order, OrderStatusEvent


@transaction.atomic
def cancel_production_booking(*, order_id, actor, reason, correlation_id, idempotency_key):
    _require_cancel_permission(actor)
    key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Booking cancellation requires a reason.")
    order = Order.objects.select_for_update().get(pk=order_id)
    previous = OrderStatusEvent.objects.filter(idempotency_key=key).first()
    if previous:
        if (previous.order_id != order.pk or previous.actor_id != actor.pk or previous.reason != reason
                or previous.correlation_id != correlation_id or previous.new_status != "CANCELLED"):
            raise ValidationError("Cancellation idempotency key was reused with different input.")
        return order
    lines = tuple(order.lines.order_by("line_number"))
    if (order.channel != "POS" or order.status != "CONFIRMED" or order.payment.state != "CONFIRMED"
            or not lines or any(line.supply_mode != "PRE_ORDER" or not line.production_batch_id for line in lines)):
        raise ValidationError("Only a confirmed production booking can use this cancellation path.")
    list(ProductionBatch.objects.select_for_update().filter(
        pk__in={line.production_batch_id for line in lines}).order_by("pk"))
    for line in lines:
        commitment = Commitment.objects.select_for_update().get(order_line=line)
        if (commitment.state != "ACTIVE" or commitment.supplied_quantity
                or commitment.outstanding_quantity != line.outstanding_quantity
                or hasattr(commitment, "reservation")):
            raise ValidationError("Booking commitment is inconsistent or already supplied.")
        quantity, base = commitment.outstanding_quantity, commitment.outstanding_base_quantity
        commitment.cancelled_quantity += quantity
        commitment.cancelled_base_quantity += base
        commitment.outstanding_quantity = 0
        commitment.outstanding_base_quantity = Decimal("0.000")
        commitment.state = "CANCELLED"
        commitment.save(_commitment_service_write=True)
        CommitmentEvent(
            commitment=commitment, previous_state="ACTIVE", new_state="CANCELLED",
            commercial_quantity=quantity, base_quantity=base, actor=actor, reason=reason,
            source_type="ORDER_CANCELLATION", source_reference=order.order_number,
            correlation_id=correlation_id, idempotency_key=_child_key(key, "commitment-cancel", line.pk),
        ).save(_commitment_service_write=True)
        line.outstanding_quantity = 0
        line.save(_cancellation_service_write=True)
    order.status = "CANCELLED"
    order.save(_cancellation_service_write=True)
    OrderStatusEvent(order=order, previous_status="CONFIRMED", new_status="CANCELLED", actor=actor,
                     reason=reason, correlation_id=correlation_id, idempotency_key=key).save(_cancellation_service_write=True)
    return order
