import hashlib
import json
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.commitments.models import Commitment
from apps.commitments.services import _create_commitment_for_confirmation
from apps.core.idempotency import lock_idempotency_key
from apps.inventory.availability import AvailabilityUnavailable, eligible_stock_positions, get_ready_availability
from apps.inventory.models import InventoryItem, Reservation, SourceAllocation
from apps.inventory.reservations import reserve_and_allocate_ready_commitment
from apps.orders.models import Order, OrderLine, OrderStatusEvent

from .models import Payment, PaymentEvidence, PaymentStatusEvent, PaymentVerificationAttempt


SOURCE_TYPE = "ORDER_CONFIRMATION"


def _require_permissions(actor):
    if actor is None or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied("Order confirmation requires an authenticated active staff actor.")
    for permission in ("payments.verify", "commitments.allocate"):
        if not actor.has_perm(permission):
            raise PermissionDenied(f"Order confirmation requires {permission}.")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _normalize_request(
    *, order_id, payment_id, evidence_id, provider_reference, actor,
    correlation_id, idempotency_key, reason,
):
    _require_permissions(actor)
    provider_reference = (provider_reference or "").strip().upper()
    reason = (reason or "").strip()
    if not provider_reference or len(provider_reference) > 64:
        raise ValidationError("An accepted M-Pesa provider reference of at most 64 characters is required.")
    if not reason:
        raise ValidationError("A verification reason is required.")
    values = {
        "order_id": _uuid(order_id, "order_id"),
        "payment_id": _uuid(payment_id, "payment_id"),
        "evidence_id": _uuid(evidence_id, "evidence_id"),
        "provider_reference": provider_reference,
        "actor_id": str(actor.pk),
        "correlation_id": _uuid(correlation_id, "correlation_id"),
        "idempotency_key": _uuid(idempotency_key, "idempotency_key"),
        "reason": reason,
    }
    fingerprint_payload = {
        key: str(value) for key, value in values.items() if key != "idempotency_key"
    }
    values["fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return values


def _validate_pending_facts(*, order, payment, evidence):
    if payment.order_id != order.pk:
        raise ValidationError("Payment does not belong to the Order.")
    if evidence.payment_id != payment.pk or not (evidence.reference_claim or evidence.has_message):
        raise ValidationError("Valid submitted evidence for this Payment is required.")
    if order.status != Order.Status.PENDING or payment.state != Payment.State.PENDING:
        raise ValidationError("Only a PENDING Order and Payment can be confirmed.")
    lines = tuple(order.lines.order_by("line_number"))
    if not lines:
        raise ValidationError("An Order without lines cannot be confirmed.")
    if any(line.supply_mode != OrderLine.SupplyMode.READY for line in lines):
        raise ValidationError("Phase 1F confirms only Orders whose complete supply mode is READY.")
    if any(line.confirmed_quantity or line.outstanding_quantity for line in lines):
        raise ValidationError("A PENDING Order cannot already contain confirmed quantities.")
    line_total = sum((line.line_total for line in lines), Decimal("0.00"))
    if line_total != order.total_amount or payment.amount != order.total_amount:
        raise ValidationError("Payment amount and immutable Order totals must agree.")
    if order.currency != Order.Currency.KES or payment.currency != Payment.Currency.KES:
        raise ValidationError("Phase 1F supports KES Orders and Payments only.")
    if payment.method != Payment.Method.MPESA:
        raise ValidationError("Phase 1F supports M-Pesa verification only.")
    return lines


def _attempt_matches(attempt, values, actor):
    return (
        attempt.payment_id == values["payment_id"]
        and attempt.evidence_id == values["evidence_id"]
        and attempt.actor_id == actor.pk
        and attempt.outcome == PaymentVerificationAttempt.Outcome.APPROVED
        and attempt.reason == values["reason"]
        and attempt.provider_reference == values["provider_reference"]
        and attempt.correlation_id == values["correlation_id"]
        and attempt.request_fingerprint == values["fingerprint"]
    )


@transaction.atomic
def _persist_accepted_verification(*, values, actor):
    lock_idempotency_key(values["idempotency_key"])
    payment = Payment.objects.select_for_update().get(pk=values["payment_id"])
    order = Order.objects.select_for_update().get(pk=values["order_id"])
    existing = PaymentVerificationAttempt.objects.filter(
        idempotency_key=values["idempotency_key"]
    ).first()
    if existing is not None:
        if not _attempt_matches(existing, values, actor):
            raise ValidationError("The confirmation idempotency key was reused with different input.")
        return existing
    try:
        evidence = PaymentEvidence.objects.get(pk=values["evidence_id"])
    except PaymentEvidence.DoesNotExist as error:
        raise ValidationError("Payment evidence does not exist.") from error
    _validate_pending_facts(order=order, payment=payment, evidence=evidence)
    if Payment.objects.filter(
        method=Payment.Method.MPESA,
        provider_reference=values["provider_reference"],
    ).exclude(pk=payment.pk).exists():
        raise ValidationError("This M-Pesa provider reference has already confirmed another Payment.")
    attempt = PaymentVerificationAttempt(
        payment=payment,
        evidence=evidence,
        actor=actor,
        outcome=PaymentVerificationAttempt.Outcome.APPROVED,
        reason=values["reason"],
        provider_reference=values["provider_reference"],
        request_fingerprint=values["fingerprint"],
        correlation_id=values["correlation_id"],
        idempotency_key=values["idempotency_key"],
    )
    attempt.save(_approved_service_write=True)
    return attempt


def _child_key(parent_key, label, object_id=None):
    suffix = label if object_id is None else f"{label}:{object_id}"
    return uuid.uuid5(parent_key, suffix)


def _validate_completed_result(*, order, payment, attempt):
    if order.status != Order.Status.CONFIRMED or payment.state != Payment.State.CONFIRMED:
        raise ValidationError("The prior confirmation result is incomplete.")
    if payment.provider_reference != attempt.provider_reference or payment.verified_by_id != attempt.actor_id:
        raise ValidationError("The prior Payment confirmation does not match its accepted verification.")
    lines = tuple(order.lines.order_by("line_number"))
    if any(
        line.confirmed_quantity != line.quantity or line.outstanding_quantity != line.quantity
        for line in lines
    ):
        raise ValidationError("The prior Order Line confirmation result is incomplete.")
    for line in lines:
        try:
            commitment = line.commitment
            reservation = commitment.reservation
        except (Commitment.DoesNotExist, Reservation.DoesNotExist) as error:
            raise ValidationError("The prior READY supply result is incomplete.") from error
        if (
            commitment.creation_idempotency_key
            != _child_key(attempt.idempotency_key, "commitment", line.pk)
            or reservation.creation_idempotency_key
            != _child_key(attempt.idempotency_key, "reservation", line.pk)
            or commitment.creation_correlation_id != attempt.correlation_id
            or reservation.creation_correlation_id != attempt.correlation_id
            or reservation.initial_base_quantity != commitment.committed_base_quantity
        ):
            raise ValidationError("The prior READY supply result does not match this confirmation.")
        allocated = reservation.allocations.aggregate(total=Sum("remaining_base_quantity"))["total"]
        if allocated != reservation.remaining_base_quantity:
            raise ValidationError("The prior Source Allocation result is incomplete.")
    if not PaymentStatusEvent.objects.filter(
        payment=payment,
        previous_state=Payment.State.PENDING,
        new_state=Payment.State.CONFIRMED,
        actor_id=attempt.actor_id,
        correlation_id=attempt.correlation_id,
        idempotency_key=_child_key(attempt.idempotency_key, "payment-status"),
    ).exists() or not OrderStatusEvent.objects.filter(
        order=order,
        previous_status=Order.Status.PENDING,
        new_status=Order.Status.CONFIRMED,
        actor_id=attempt.actor_id,
        correlation_id=attempt.correlation_id,
        idempotency_key=_child_key(attempt.idempotency_key, "order-status"),
    ).exists():
        raise ValidationError("The prior confirmation status history is incomplete.")
    return order


@transaction.atomic
def _confirm_ready_order(*, values, actor, attempt):
    payment = Payment.objects.select_for_update().get(pk=values["payment_id"])
    order = Order.objects.select_for_update().get(pk=values["order_id"])
    if order.status == Order.Status.CONFIRMED or payment.state == Payment.State.CONFIRMED:
        return _validate_completed_result(order=order, payment=payment, attempt=attempt)
    evidence = PaymentEvidence.objects.get(pk=values["evidence_id"])
    lines = tuple(
        OrderLine.objects.select_for_update()
        .filter(order=order)
        .select_related("product", "sale_unit")
        .order_by("line_number")
    )
    _validate_pending_facts(order=order, payment=payment, evidence=evidence)
    if not _attempt_matches(attempt, values, actor):
        raise ValidationError("Accepted verification does not match this confirmation request.")

    product_ids = sorted({line.product_id for line in lines}, key=str)
    items = list(
        InventoryItem.objects.select_for_update()
        .filter(product_id__in=product_ids)
        .select_related("product")
        .order_by("pk")
    )
    if len(items) != len(product_ids):
        raise ValidationError("Every Order Line Product requires an Inventory Item.")
    for item in items:
        if not item.is_active or item.base_unit != item.product.base_inventory_unit:
            raise ValidationError("Every Order Line requires an active compatible Inventory Item.")
    for item in items:
        list(
            eligible_stock_positions(
                inventory_item=item,
                business_date=timezone.localdate(),
            ).select_for_update().order_by("pk")
        )

    confirmed_at = attempt.created_at
    for line in lines:
        try:
            available = get_ready_availability(product=line.product, sale_unit=line.sale_unit)
        except AvailabilityUnavailable as error:
            raise ValidationError(str(error)) from error
        if available.available_sale_units < line.quantity:
            raise ValidationError("Insufficient READY availability for complete Order confirmation.")
        commitment = _create_commitment_for_confirmation(
            order_line_id=line.pk,
            actor=actor,
            confirmed_at=confirmed_at,
            correlation_id=values["correlation_id"],
            idempotency_key=_child_key(values["idempotency_key"], "commitment", line.pk),
            reason=values["reason"],
            source_type=SOURCE_TYPE,
            source_reference=order.order_number,
        )
        reserve_and_allocate_ready_commitment(
            commitment_id=commitment.id,
            actor=actor,
            correlation_id=values["correlation_id"],
            idempotency_key=_child_key(values["idempotency_key"], "reservation", line.pk),
            reason=values["reason"],
            source_type=SOURCE_TYPE,
            source_reference=order.order_number,
            approved_sources=None,
            _confirmation_order_locked=True,
        )
        line.confirmed_quantity = line.quantity
        line.outstanding_quantity = line.quantity
        line.save(_confirmation_service_write=True)

    payment.state = Payment.State.CONFIRMED
    payment.provider_reference = values["provider_reference"]
    payment.verified_by = actor
    payment.verified_at = confirmed_at
    payment.save(_confirmation_service_write=True)
    PaymentStatusEvent(
        payment=payment,
        previous_state=Payment.State.PENDING,
        new_state=Payment.State.CONFIRMED,
        actor=actor,
        reason=values["reason"],
        correlation_id=values["correlation_id"],
        idempotency_key=_child_key(values["idempotency_key"], "payment-status"),
    ).save(_confirmation_service_write=True)
    order.status = Order.Status.CONFIRMED
    order.save(_confirmation_service_write=True)
    OrderStatusEvent(
        order=order,
        previous_status=Order.Status.PENDING,
        new_status=Order.Status.CONFIRMED,
        actor=actor,
        reason=values["reason"],
        correlation_id=values["correlation_id"],
        idempotency_key=_child_key(values["idempotency_key"], "order-status"),
    ).save(_confirmation_service_write=True)
    return order


def verify_payment_and_confirm_order(
    *, order_id, payment_id, evidence_id, provider_reference, actor,
    correlation_id, idempotency_key, reason,
):
    """Persist staff acceptance, then atomically establish the complete READY promise."""
    non_test_atomic = any(
        not getattr(block, "_from_testcase", False) for block in connection.atomic_blocks
    )
    if non_test_atomic:
        raise ValidationError(
            "Confirmation must own its transaction so accepted verification history can persist."
        )
    values = _normalize_request(
        order_id=order_id,
        payment_id=payment_id,
        evidence_id=evidence_id,
        provider_reference=provider_reference,
        actor=actor,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        reason=reason,
    )
    attempt = _persist_accepted_verification(values=values, actor=actor)
    return _confirm_ready_order(values=values, actor=actor, attempt=attempt)
