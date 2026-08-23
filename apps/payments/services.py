import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.idempotency import lock_idempotency_key

from .models import Payment, PaymentEvidence, PaymentVerificationAttempt


def _require_permission(actor, permission):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"This action requires {permission}.")


@transaction.atomic
def submit_payment_evidence(
    *, payment, submission_source, reference_claim="", submitted_message="", actor=None
):
    """Persist untrusted evidence without logging or treating it as confirmation."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.state != Payment.State.PENDING:
        raise ValidationError("Evidence can be submitted only for a pending Payment.")
    if submission_source == PaymentEvidence.SubmissionSource.POS:
        _require_permission(actor, "pos.process_sale")
    elif submission_source == PaymentEvidence.SubmissionSource.STAFF:
        _require_permission(actor, "payments.verify")
    elif submission_source != PaymentEvidence.SubmissionSource.ECOMMERCE:
        raise ValidationError("Payment evidence submission source is invalid.")

    return PaymentEvidence.objects.create(
        payment=payment,
        reference_claim=reference_claim,
        submitted_message=submitted_message,
        submission_source=submission_source,
    )


@transaction.atomic
def record_rejected_verification_attempt(
    *, payment, evidence, actor, reason, idempotency_key
):
    """Record a rejection only; successful verification is deliberately unavailable."""
    _require_permission(actor, "payments.verify")
    key = lock_idempotency_key(idempotency_key)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.state != Payment.State.PENDING:
        raise ValidationError("Only pending Payments can receive a verification attempt.")
    if evidence.payment_id != payment.id:
        raise ValidationError("Verification evidence must belong to the Payment.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("A rejection reason is required.")

    existing = PaymentVerificationAttempt.objects.filter(idempotency_key=key).first()
    if existing is not None:
        if (
            existing.payment_id != payment.id
            or existing.evidence_id != evidence.id
            or existing.actor_id != actor.id
            or existing.reason != reason
            or existing.outcome != PaymentVerificationAttempt.Outcome.REJECTED
        ):
            raise ValidationError("The verification idempotency key was reused for different input.")
        return existing

    attempt = PaymentVerificationAttempt(
        payment=payment,
        evidence=evidence,
        actor=actor,
        outcome=PaymentVerificationAttempt.Outcome.REJECTED,
        reason=reason,
        idempotency_key=key,
    )
    attempt.save(_rejected_service_write=True)
    return attempt


# Public Phase 1F command boundary; kept here for callers of the existing service module.
from .confirmation import verify_payment_and_confirm_order  # noqa: E402,F401
