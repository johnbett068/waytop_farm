"""One cashier acceptance command; no external-provider verification is simulated."""
import hashlib
import json
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key
from apps.commitments.supply import supply_ready_commitment
from apps.orders.models import Order
from apps.orders.services import _require_pos_permission, create_pending_order
from .confirmation import _require_permissions, establish_confirmation
from .models import Payment, PaymentVerificationAttempt
from .services import submit_payment_evidence


def normalize_payment(method, reference):
    if method not in Payment.Method.values:
        raise ValidationError("Select Cash or M-Pesa.")
    reference = (reference or "").strip().upper()
    if method == Payment.Method.MPESA and (not reference or len(reference) > 64):
        raise ValidationError("An M-Pesa reference of at most 64 characters is required.")
    if method == Payment.Method.CASH and reference:
        raise ValidationError("Cash does not use an M-Pesa reference.")
    return reference or None


@transaction.atomic
def confirm_pos_payment(*, order_id, method, reference, actor, idempotency_key):
    _require_pos_permission(actor)
    _require_permissions(actor)
    key = lock_idempotency_key(idempotency_key)
    reference = normalize_payment(method, reference)
    # Match the established Payment -> Order confirmation lock order.
    payment = Payment.objects.select_for_update().get(order_id=order_id)
    order = Order.objects.select_for_update().get(pk=order_id, channel=Order.Channel.POS)
    fingerprint = hashlib.sha256(json.dumps({
        "order": str(order.pk), "method": method, "reference": reference, "actor": str(actor.pk),
    }, sort_keys=True).encode()).hexdigest()
    if payment.pos_confirmation_key is not None:
        if (payment.pos_confirmation_key != key or payment.pos_confirmation_fingerprint != fingerprint
                or payment.state != Payment.State.CONFIRMED):
            raise ValidationError("Payment idempotency key was reused with different input.")
        return order
    if Payment.objects.filter(pos_confirmation_key=key).exists():
        raise ValidationError("Payment idempotency key belongs to another transaction.")
    if order.status != Order.Status.PENDING or payment.state != Payment.State.PENDING:
        raise ValidationError("Only a pending Order and Payment can be confirmed.")
    if method != payment.method:
        raise ValidationError("Payment method must match the pending transaction.")
    lines = tuple(order.lines.select_for_update().select_related("product", "sale_unit").order_by("line_number"))
    modes = {line.supply_mode for line in lines}
    if modes not in ({"READY"}, {"PRE_ORDER"}):
        raise ValidationError("Sales and Bookings cannot be mixed.")
    booking = modes == {"PRE_ORDER"}
    if any(line.confirmed_quantity or line.outstanding_quantity for line in lines):
        raise ValidationError("Pending lines must not already be confirmed.")
    if sum(line.line_total for line in lines) != order.total_amount or payment.amount != order.total_amount:
        raise ValidationError("Payment and Order totals must agree.")
    if payment.currency != "KES" or order.currency != "KES":
        raise ValidationError("Only KES payments are supported.")
    if method == Payment.Method.MPESA and Payment.objects.filter(method=method, provider_reference=reference).exclude(pk=payment.pk).exists():
        raise ValidationError("This M-Pesa reference has already confirmed another Payment.")
    reason = "POS cashier confirmed cash received." if method == "CASH" else "POS cashier accepted M-Pesa reference."
    correlation = uuid.uuid5(key, "pos-confirmation")
    confirmed_at = timezone.now()
    if method == Payment.Method.MPESA:
        evidence = submit_payment_evidence(payment=payment, submission_source="POS", reference_claim=reference, actor=actor)
        PaymentVerificationAttempt(
            payment=payment, evidence=evidence, actor=actor, outcome="APPROVED", reason=reason,
            provider_reference=reference, request_fingerprint=fingerprint,
            correlation_id=correlation, idempotency_key=key,
        ).save(_approved_service_write=True)
    payment.pos_confirmation_key = key
    payment.pos_confirmation_fingerprint = fingerprint
    return establish_confirmation(
        order=order, payment=payment, lines=lines, actor=actor, confirmed_at=confirmed_at, booking=booking,
        values={"idempotency_key": key, "correlation_id": correlation, "reason": reason, "provider_reference": reference},
    )


@transaction.atomic
def checkout_pos(*, lines, location_id, customer, method, reference, actor, idempotency_key, activity):
    _require_pos_permission(actor)
    _require_permissions(actor)
    key = lock_idempotency_key(idempotency_key)
    normalize_payment(method, reference)
    lines = tuple(lines)
    if activity not in ("sales", "bookings") or not lines:
        raise ValidationError("Select Sales or Bookings and add products.")
    expected_mode = "READY" if activity == "sales" else "PRE_ORDER"
    if any(line.supply_mode != expected_mode or bool(line.production_batch_id) != (activity == "bookings") for line in lines):
        raise ValidationError("Cart transaction type does not match the checkout activity.")
    order = create_pending_order(
        channel="POS", fulfillment_method="CUSTOMER_COLLECTION", lines=lines,
        location_id=location_id, customer=customer, actor=actor,
        creation_idempotency_key=key, payment_method=method,
    )
    order = confirm_pos_payment(order_id=order.pk, method=method, reference=reference,
                                actor=actor, idempotency_key=uuid.uuid5(key, "payment"))
    if activity == "sales":
        # Reuse the ledger service and stable command identities on retries.
        # Payment and all line issues commit together or all roll back.
        for commitment in order.commitments.select_related("order_line").order_by("order_line__line_number"):
            supply_ready_commitment(
                commitment_id=commitment.id,
                commercial_quantity=commitment.committed_quantity,
                actor=actor, correlation_id=uuid.uuid5(key, "pos-sale"),
                idempotency_key=uuid.uuid5(key, f"pos-issue:{commitment.order_line_id}"),
                reason="POS sale completed", source_type="POS_SALE",
                source_reference=order.order_number,
            )
    return order
