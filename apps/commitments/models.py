import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class ProtectedCommitmentQuerySet(models.QuerySet):
    """Reject ORM mutation paths outside Commitment domain services."""

    def _reject_write(self):
        raise ValidationError("Commitments and Commitment history require a domain service.")

    def update(self, **kwargs):
        self._reject_write()

    def delete(self):
        self._reject_write()

    def bulk_create(self, objs, **kwargs):
        self._reject_write()

    def bulk_update(self, objs, fields, **kwargs):
        self._reject_write()


class Commitment(models.Model):
    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SATISFIED = "SATISFIED", "Satisfied"
        CANCELLED = "CANCELLED", "Cancelled"

    # The database-generated primary key is also the monotonic FIFO tie-breaker.
    fifo_sequence = models.BigAutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="commitments"
    )
    order_line = models.OneToOneField(
        "orders.OrderLine", on_delete=models.PROTECT, related_name="commitment"
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem", on_delete=models.PROTECT, related_name="commitments"
    )
    committed_quantity = models.PositiveBigIntegerField()
    base_quantity_per_sale_unit = models.DecimalField(max_digits=12, decimal_places=3)
    committed_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    supplied_quantity = models.PositiveBigIntegerField(default=0)
    supplied_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    cancelled_quantity = models.PositiveBigIntegerField(default=0)
    cancelled_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    outstanding_quantity = models.PositiveBigIntegerField()
    outstanding_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    state = models.CharField(max_length=10, choices=State.choices, default=State.ACTIVE)
    confirmed_at = models.DateTimeField()
    required_date = models.DateField(blank=True, null=True)
    creation_correlation_id = models.UUIDField(editable=False)
    creation_idempotency_key = models.UUIDField(editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedCommitmentQuerySet.as_manager()

    class Meta:
        ordering = ("confirmed_at", "fifo_sequence")
        permissions = (
            ("view", "Can view commitments"),
            ("allocate", "Can allocate commitments"),
        )
        indexes = [
            models.Index(
                fields=("inventory_item", "confirmed_at", "fifo_sequence"),
                name="commitment_fifo_pool_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(committed_quantity__gt=0),
                name="commitment_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(base_quantity_per_sale_unit__gt=0),
                name="commitment_base_per_unit_positive",
            ),
            models.CheckConstraint(
                condition=Q(committed_base_quantity__gt=0),
                name="commitment_base_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(supplied_base_quantity__gte=0),
                name="commitment_supplied_base_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(cancelled_base_quantity__gte=0),
                name="commitment_cancelled_base_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(outstanding_base_quantity__gte=0),
                name="commitment_outstanding_base_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(
                    committed_quantity=(
                        F("supplied_quantity")
                        + F("cancelled_quantity")
                        + F("outstanding_quantity")
                    )
                ),
                name="commitment_commercial_quantity_equation",
            ),
            models.CheckConstraint(
                condition=Q(
                    committed_base_quantity=(
                        F("supplied_base_quantity")
                        + F("cancelled_base_quantity")
                        + F("outstanding_base_quantity")
                    )
                ),
                name="commitment_base_quantity_equation",
            ),
            models.CheckConstraint(
                condition=Q(
                    committed_base_quantity=F("committed_quantity")
                    * F("base_quantity_per_sale_unit")
                ),
                name="commitment_exact_base_conversion",
            ),
            models.CheckConstraint(
                condition=Q(
                    supplied_base_quantity=F("supplied_quantity")
                    * F("base_quantity_per_sale_unit")
                ),
                name="commitment_supplied_conversion",
            ),
            models.CheckConstraint(
                condition=Q(
                    cancelled_base_quantity=F("cancelled_quantity")
                    * F("base_quantity_per_sale_unit")
                ),
                name="commitment_cancelled_conversion",
            ),
            models.CheckConstraint(
                condition=Q(
                    outstanding_base_quantity=F("outstanding_quantity")
                    * F("base_quantity_per_sale_unit")
                ),
                name="commitment_outstanding_conversion",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="ACTIVE", outstanding_quantity__gt=0)
                    | Q(
                        state="SATISFIED",
                        outstanding_quantity=0,
                        cancelled_quantity=0,
                    )
                    | Q(state="CANCELLED", outstanding_quantity=0, cancelled_quantity__gt=0)
                ),
                name="commitment_state_quantity_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_line_id and self.order_id and self.order_line.order_id != self.order_id:
            errors["order_line"] = "Commitment Order Line must belong to its Order."
        if (
            self.inventory_item_id
            and self.order_line_id
            and self.inventory_item.product_id != self.order_line.product_id
        ):
            errors["inventory_item"] = "Commitment Inventory Item must map to the Order Line Product."
        if self.order_line_id:
            if self.committed_quantity != self.order_line.quantity:
                errors["committed_quantity"] = "Committed quantity must match the Order Line snapshot."
            if self.base_quantity_per_sale_unit != self.order_line.base_quantity:
                errors["base_quantity_per_sale_unit"] = (
                    "Base quantity per Sale Unit must match the Order Line snapshot."
                )
            if self.order_line.supply_mode == self.order_line.SupplyMode.READY:
                if self.required_date is not None:
                    errors["required_date"] = "READY Commitments cannot have a required date."
            elif self.required_date != self.order.required_date:
                errors["required_date"] = (
                    "PRE_ORDER Commitment required date must copy the Order required date."
                )
        if self.confirmed_at and (
            not hasattr(self.confirmed_at, "utcoffset")
            or timezone.is_naive(self.confirmed_at)
        ):
            errors["confirmed_at"] = "Confirmation time must be timezone-aware."
        if self._state.adding and (
            self.state != self.State.ACTIVE
            or self.supplied_quantity != 0
            or self.supplied_base_quantity != 0
            or self.cancelled_quantity != 0
            or self.cancelled_base_quantity != 0
            or self.outstanding_quantity != self.committed_quantity
            or self.outstanding_base_quantity != self.committed_base_quantity
        ):
            errors["state"] = "A new Commitment must begin fully outstanding and ACTIVE."
        if not self._state.adding:
            original = type(self).objects.filter(id=self.id).first()
            if original is None:
                errors["id"] = "A Commitment's UUID identity is immutable."
            else:
                immutable_fields = (
                    "fifo_sequence",
                    "id",
                    "order_id",
                    "order_line_id",
                    "inventory_item_id",
                    "committed_quantity",
                    "base_quantity_per_sale_unit",
                    "committed_base_quantity",
                    "confirmed_at",
                    "required_date",
                    "creation_correlation_id",
                    "creation_idempotency_key",
                )
                if any(
                    getattr(self, field) != getattr(original, field)
                    for field in immutable_fields
                ):
                    errors["id"] = "Immutable Commitment identity or snapshot fields changed."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_commitment_service_write", False)
        if not service_write:
            raise ValidationError("Commitments require a controlled domain service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commitments cannot be deleted.")

    def __str__(self):
        return f"Commitment {self.id} for {self.order.order_number}"


class CommitmentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commitment = models.ForeignKey(
        Commitment, on_delete=models.PROTECT, related_name="events"
    )
    previous_state = models.CharField(
        max_length=10, choices=Commitment.State.choices, blank=True, null=True
    )
    new_state = models.CharField(max_length=10, choices=Commitment.State.choices)
    commercial_quantity = models.PositiveBigIntegerField()
    base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commitment_events",
    )
    reason = models.TextField()
    source_type = models.CharField(max_length=50)
    source_reference = models.CharField(max_length=160)
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedCommitmentQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("commitment",),
                condition=Q(previous_state__isnull=True),
                name="commitment_one_initial_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(previous_state__isnull=True, new_state="ACTIVE")
                    | Q(previous_state="ACTIVE", new_state="CANCELLED")
                ),
                name="commitment_event_valid_transition",
            ),
            models.CheckConstraint(
                condition=Q(commercial_quantity__gt=0),
                name="commitment_event_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(base_quantity__gt=0),
                name="commitment_event_base_positive",
            ),
            models.CheckConstraint(
                condition=~Q(reason=""), name="commitment_event_reason_not_empty"
            ),
            models.CheckConstraint(
                condition=~Q(source_type=""),
                name="commitment_event_source_type_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(source_reference=""),
                name="commitment_event_source_ref_not_empty",
            ),
        ]

    def clean(self):
        super().clean()
        self.reason = (self.reason or "").strip()
        self.source_type = (self.source_type or "").strip()
        self.source_reference = (self.source_reference or "").strip()
        errors = {}
        for field in ("reason", "source_type", "source_reference"):
            if not getattr(self, field):
                errors[field] = "This Commitment audit field is required."
        if self.commitment_id:
            initial = self.previous_state is None and self.new_state == Commitment.State.ACTIVE
            cancellation = (
                self.previous_state == Commitment.State.ACTIVE
                and self.new_state == Commitment.State.CANCELLED
            )
            if not (initial or cancellation):
                errors["new_state"] = "Commitment event transition is invalid."
            elif initial and (
                self.commercial_quantity != self.commitment.committed_quantity
                or self.base_quantity != self.commitment.committed_base_quantity
                or self.correlation_id != self.commitment.creation_correlation_id
                or self.idempotency_key != self.commitment.creation_idempotency_key
            ):
                errors["commercial_quantity"] = (
                    "Initial Commitment event must match its Commitment creation facts."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_commitment_service_write", False)
        if not service_write:
            raise ValidationError("Commitment events may be created only by a domain service.")
        if not self._state.adding:
            raise ValidationError("Commitment events are append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commitment events cannot be deleted.")

    def __str__(self):
        return f"Commitment event {self.id}"


class CommitmentSupplyEvent(models.Model):
    """Immutable evidence of physical supply against one READY Commitment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commitment = models.ForeignKey(
        Commitment,
        on_delete=models.PROTECT,
        related_name="supply_events",
    )
    inventory_movement = models.OneToOneField(
        "inventory.InventoryMovement",
        on_delete=models.PROTECT,
        related_name="commitment_supply_event",
    )
    previous_state = models.CharField(max_length=10, choices=Commitment.State.choices)
    new_state = models.CharField(max_length=10, choices=Commitment.State.choices)
    commercial_quantity = models.PositiveBigIntegerField()
    base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commitment_supply_events",
    )
    reason = models.TextField()
    source_type = models.CharField(max_length=50)
    source_reference = models.CharField(max_length=160)
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(editable=False, unique=True)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedCommitmentQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(commercial_quantity__gt=0),
                name="supply_event_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(base_quantity__gt=0),
                name="supply_event_base_positive",
            ),
            models.CheckConstraint(
                condition=~Q(reason=""),
                name="supply_event_reason_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(source_type=""),
                name="supply_event_source_type_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(source_reference=""),
                name="supply_event_source_ref_not_empty",
            ),
        ]

    def clean(self):
        super().clean()
        self.reason = (self.reason or "").strip()
        self.source_type = (self.source_type or "").strip()
        self.source_reference = (self.source_reference or "").strip()
        errors = {}
        if not self.reason:
            errors["reason"] = "Supply reason is required."
        if not self.source_type:
            errors["source_type"] = "Supply source type is required."
        if not self.source_reference:
            errors["source_reference"] = "Supply source reference is required."
        if self.commitment_id:
            expected = Decimal(self.commercial_quantity) * self.commitment.base_quantity_per_sale_unit
            if self.base_quantity != expected:
                errors["base_quantity"] = (
                    "Supply base quantity must exactly match the Commitment conversion."
                )
        if self.inventory_movement_id and self.inventory_movement.movement_type != "ISSUE":
            errors["inventory_movement"] = "Physical supply must reference an ISSUE movement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_commitment_service_write", False)
        if not service_write or not self._state.adding:
            raise ValidationError("Commitment supply events are append-only service records.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commitment supply events cannot be deleted.")

    def __str__(self):
        return f"Supply event {self.id} for {self.commitment.id}"
