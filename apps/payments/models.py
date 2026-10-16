import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .fields import EncryptedTextField


class ProtectedPaymentQuerySet(models.QuerySet):
    def _reject_write(self):
        raise ValidationError("Payment facts and history require a controlled domain service.")

    def update(self, **kwargs):
        self._reject_write()

    def delete(self):
        self._reject_write()

    def bulk_create(self, objs, **kwargs):
        self._reject_write()

    def bulk_update(self, objs, fields, **kwargs):
        self._reject_write()


class ImmutableRecordMixin(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(f"{type(self).__name__} records are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f"{type(self).__name__} records cannot be deleted.")


class Payment(models.Model):
    class Method(models.TextChoices):
        MPESA = "MPESA", "M-Pesa"
        CASH = "CASH", "Cash"

    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"

    class Currency(models.TextChoices):
        KES = "KES", "Kenyan shilling"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="payment")
    amount = models.DecimalField(max_digits=18, decimal_places=2, editable=False)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.KES, editable=False)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.MPESA, editable=False)
    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING, editable=False)
    provider_reference = models.CharField(max_length=64, blank=True, null=True, editable=False)
    pos_confirmation_key = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    pos_confirmation_fingerprint = models.CharField(max_length=64, blank=True, default="", editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_payments",
        blank=True,
        null=True,
        editable=False,
    )
    verified_at = models.DateTimeField(blank=True, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProtectedPaymentQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        permissions = (("verify", "Can verify payments"),)
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(condition=Q(currency="KES"), name="payment_currency_kes"),
            models.CheckConstraint(condition=Q(method__in=["MPESA", "CASH"]), name="payment_method_supported"),
            models.CheckConstraint(
                condition=(
                    Q(
                        state="PENDING",
                        provider_reference__isnull=True,
                        verified_by__isnull=True,
                        verified_at__isnull=True,
                    )
                    | Q(
                        state="CONFIRMED",
                        method="MPESA",
                        provider_reference__isnull=False,
                        verified_by__isnull=False,
                        verified_at__isnull=False,
                    )
                    | Q(state="CONFIRMED", method="CASH", provider_reference__isnull=True,
                        verified_by__isnull=False, verified_at__isnull=False)
                ),
                name="payment_confirmation_metadata_consistent",
            ),
            models.UniqueConstraint(
                fields=("method", "provider_reference"),
                condition=Q(provider_reference__isnull=False),
                name="payment_confirmed_provider_reference_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if self.order_id and self.amount != self.order.total_amount:
            raise ValidationError({"amount": "Payment amount must equal the Order total."})
        if self.provider_reference:
            self.provider_reference = self.provider_reference.strip().upper()
        if self.method == self.Method.CASH and self.provider_reference is not None:
            raise ValidationError({"provider_reference": "Cash does not use an M-Pesa reference."})
        if self.state == self.State.CONFIRMED and self.method == self.Method.MPESA and not self.provider_reference:
            raise ValidationError({"provider_reference": "Confirmed M-Pesa requires a reference."})
        if self._state.adding and self.state != self.State.PENDING:
            raise ValidationError({"state": "A new payment must be pending."})

    def save(self, *args, **kwargs):
        confirmation_write = kwargs.pop("_confirmation_service_write", False)
        if not self._state.adding and not confirmation_write:
            raise ValidationError("Pending payments are immutable until the atomic confirmation service exists.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payments cannot be deleted.")

    def __str__(self):
        return f"Payment for {self.order.order_number}"


class PaymentEvidence(ImmutableRecordMixin):
    class SubmissionSource(models.TextChoices):
        ECOMMERCE = "ECOMMERCE", "Ecommerce"
        POS = "POS", "Point of Sale"
        STAFF = "STAFF", "Authorized staff entry"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="evidence")
    reference_claim = models.CharField(max_length=128, blank=True)
    submitted_message = EncryptedTextField(blank=True)
    submission_source = models.CharField(max_length=10, choices=SubmissionSource.choices)
    submitted_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedPaymentQuerySet.as_manager()

    class Meta:
        ordering = ("submitted_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(reference_claim="") | ~Q(submitted_message=""),
                name="payment_evidence_has_input",
            ),
        ]

    def clean(self):
        super().clean()
        self.reference_claim = (self.reference_claim or "").strip()
        self.submitted_message = (self.submitted_message or "").strip()
        if not self.reference_claim and not self.submitted_message:
            raise ValidationError("Payment evidence requires a reference or message.")

    @property
    def has_message(self):
        return bool(self.submitted_message)

    def __str__(self):
        return f"Payment evidence {self.pk}"


class PaymentVerificationAttempt(ImmutableRecordMixin):
    class Outcome(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="verification_attempts")
    evidence = models.ForeignKey(
        PaymentEvidence, on_delete=models.PROTECT, related_name="verification_attempts"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_verification_attempts"
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    reason = models.TextField()
    provider_reference = models.CharField(max_length=64, blank=True, default="")
    request_fingerprint = models.CharField(max_length=64, blank=True, default="", editable=False)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedPaymentQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(condition=~Q(reason=""), name="payment_verification_reason_not_empty"),
        ]

    def clean(self):
        super().clean()
        self.reason = (self.reason or "").strip()
        self.provider_reference = (self.provider_reference or "").strip().upper()
        errors = {}
        if not self.reason:
            errors["reason"] = "A verification reason is required."
        if self.evidence_id and self.payment_id and self.evidence.payment_id != self.payment_id:
            errors["evidence"] = "Verification evidence must belong to the Payment."
        approved_write = getattr(self, "_approved_service_write", False)
        rejected_write = getattr(self, "_rejected_service_write", False)
        if self.outcome == self.Outcome.APPROVED and not approved_write:
            errors["outcome"] = "Approval requires the atomic confirmation service."
        if self.outcome == self.Outcome.REJECTED and not rejected_write:
            errors["outcome"] = "Rejection requires the Payment verification service."
        if self.outcome == self.Outcome.APPROVED:
            if not self.provider_reference:
                errors["provider_reference"] = "Approved verification requires a provider reference."
            if not self.request_fingerprint:
                errors["request_fingerprint"] = "Approved verification requires a request fingerprint."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        approved_write = kwargs.pop("_approved_service_write", False)
        rejected_write = kwargs.pop("_rejected_service_write", False)
        if not self._state.adding:
            raise ValidationError("Payment verification attempts are immutable.")
        self._approved_service_write = approved_write
        self._rejected_service_write = rejected_write
        try:
            self.full_clean()
            return models.Model.save(self, *args, **kwargs)
        finally:
            del self._approved_service_write
            del self._rejected_service_write

    def __str__(self):
        return f"Verification attempt {self.pk}: {self.outcome}"


class PaymentStatusEvent(ImmutableRecordMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="status_events")
    previous_state = models.CharField(
        max_length=10, choices=Payment.State.choices, blank=True, null=True
    )
    new_state = models.CharField(max_length=10, choices=Payment.State.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_status_events",
        blank=True,
        null=True,
    )
    reason = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedPaymentQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("payment",),
                condition=Q(previous_state__isnull=True),
                name="payment_one_initial_status_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(previous_state__isnull=True, new_state="PENDING")
                    | Q(
                        previous_state="PENDING",
                        new_state="CONFIRMED",
                        actor__isnull=False,
                    )
                ),
                name="payment_status_event_valid_transition",
            ),
        ]

    def clean(self):
        super().clean()
        creation_transition = (
            getattr(self, "_creation_service_write", False)
            and self.previous_state is None
            and self.new_state == Payment.State.PENDING
        )
        confirmation_transition = (
            getattr(self, "_confirmation_service_write", False)
            and self.previous_state == Payment.State.PENDING
            and self.new_state == Payment.State.CONFIRMED
            and self.actor_id is not None
        )
        if not (creation_transition or confirmation_transition):
            raise ValidationError(
                "Payment status events require the matching domain service."
            )

    def save(self, *args, **kwargs):
        creation_write = kwargs.pop("_creation_service_write", False)
        confirmation_write = kwargs.pop("_confirmation_service_write", False)
        if not self._state.adding:
            raise ValidationError("Payment status events are immutable.")
        self._creation_service_write = creation_write
        self._confirmation_service_write = confirmation_write
        try:
            self.full_clean()
            return models.Model.save(self, *args, **kwargs)
        finally:
            del self._creation_service_write
            del self._confirmation_service_write

    def __str__(self):
        return f"{self.payment.order.order_number}: {self.new_state}"
