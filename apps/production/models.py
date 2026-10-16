import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class ProductionWriteQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Production records may be changed only through Production services.")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Production records may be created only through Production services.")

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError("Production records may be changed only through Production services.")

    def delete(self):
        raise ValidationError("Production business records cannot be deleted.")


class ServiceControlledModel:
    def save(self, *args, **kwargs):
        if not kwargs.pop("_production_service_write", False):
            raise ValidationError("Production records may be written only through Production services.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Production business records cannot be deleted.")


class ProductionBatch(ServiceControlledModel, models.Model):
    # Historical batches remain unassigned and cannot provide booking capacity.
    location = models.ForeignKey(
        "inventory.InventoryLocation", on_delete=models.PROTECT,
        related_name="production_batches", null=True, blank=True,
    )
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        IN_PRODUCTION = "IN_PRODUCTION", "In production"
        READY = "READY", "Ready"
        CLOSED = "CLOSED", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_number = models.CharField(max_length=64, unique=True)
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="production_batches"
    )
    start_date = models.DateField()
    expected_ready_date = models.DateField()
    quantity_started = models.DecimalField(max_digits=12, decimal_places=3)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_production_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductionWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-start_date", "batch_number")
        default_permissions = ()
        permissions = (
            ("view_operations", "Can view Production operations"),
            ("manage_batches", "Can manage Production batches"),
            ("record_purchases", "Can record Production purchases"),
            ("record_labour", "Can record Production labour"),
            ("record_activities", "Can record nursery activities"),
        )
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity_started__gt=0),
                name="production_batch_started_positive",
            ),
            models.CheckConstraint(
                condition=Q(current_quantity__gte=0),
                name="production_batch_current_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(current_quantity__lte=F("quantity_started")),
                name="production_batch_current_not_above_started",
            ),
            models.CheckConstraint(
                condition=Q(expected_ready_date__gte=F("start_date")),
                name="production_batch_dates_ordered",
            ),
        ]

    def clean(self):
        super().clean()
        if self.product_id and not self.product.is_active:
            raise ValidationError({"product": "Only active seedling Products may be used."})
        if self.expected_ready_date and self.start_date and self.expected_ready_date < self.start_date:
            raise ValidationError(
                {"expected_ready_date": "Expected ready date cannot precede start date."}
            )
        if self.quantity_started is not None and self.quantity_started <= 0:
            raise ValidationError({"quantity_started": "Quantity started must be positive."})
        if self.current_quantity is not None and self.current_quantity < 0:
            raise ValidationError({"current_quantity": "Current quantity cannot be negative."})
        if (
            self.quantity_started is not None
            and self.current_quantity is not None
            and self.current_quantity > self.quantity_started
        ):
            raise ValidationError({"current_quantity": "Current quantity cannot exceed quantity started."})

    def __str__(self):
        return f"{self.batch_number} — {self.product.name}"


class ProductionBatchEvent(ServiceControlledModel, models.Model):
    previous_location = models.ForeignKey(
        "inventory.InventoryLocation", on_delete=models.PROTECT,
        related_name="production_location_before_events", null=True, blank=True,
    )
    location = models.ForeignKey(
        "inventory.InventoryLocation", on_delete=models.PROTECT,
        related_name="production_location_events", null=True, blank=True,
    )
    class Operation(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Planning or quantity updated"
        TRANSITIONED = "TRANSITIONED", "Status transitioned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        ProductionBatch, on_delete=models.PROTECT, related_name="history"
    )
    operation = models.CharField(max_length=20, choices=Operation.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="production_batch_events",
    )
    reason = models.TextField()
    from_status = models.CharField(max_length=20, choices=ProductionBatch.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=ProductionBatch.Status.choices, blank=True)
    previous_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductionWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=Q(previous_quantity__isnull=True) | Q(previous_quantity__gte=0),
                name="production_event_previous_quantity_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(current_quantity__isnull=True) | Q(current_quantity__gte=0),
                name="production_event_current_quantity_non_negative",
            ),
        ]


class ProductionPurchase(ServiceControlledModel, models.Model):
    class Category(models.TextChoices):
        SEEDS = "SEEDS", "Seeds"
        GROWING_MEDIA = "GROWING_MEDIA", "Growing media"
        NURSERY_TRAYS = "NURSERY_TRAYS", "Nursery trays"
        FERTILIZER = "FERTILIZER", "Fertilizer"
        PESTICIDE = "PESTICIDE", "Pesticide"
        FUNGICIDE = "FUNGICIDE", "Fungicide"
        HERBICIDE = "HERBICIDE", "Herbicide"
        NURSERY_SUPPLIES = "NURSERY_SUPPLIES", "Nursery supplies"
        PACKAGING = "PACKAGING", "Packaging"
        OTHER = "OTHER", "Other nursery input"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_date = models.DateField()
    supplier = models.CharField(max_length=200)
    item_description = models.CharField(max_length=250)
    category = models.CharField(max_length=30, choices=Category.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=50)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    total_cost = models.DecimalField(max_digits=16, decimal_places=2, editable=False)
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.PROTECT,
        related_name="purchases",
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="production_purchases",
    )
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductionWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-purchase_date", "-created_at")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="production_purchase_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="production_purchase_unit_cost_non_negative"),
            models.CheckConstraint(condition=Q(total_cost__gte=0), name="production_purchase_total_non_negative"),
        ]


class ProductionLabour(ServiceControlledModel, models.Model):
    class EffortUnit(models.TextChoices):
        HOURS = "HOURS", "Hours"
        DAYS = "DAYS", "Days"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_date = models.DateField()
    worker = models.CharField(max_length=200)
    activity = models.CharField(max_length=250)
    effort_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    effort_unit = models.CharField(max_length=10, choices=EffortUnit.choices)
    rate = models.DecimalField(max_digits=14, decimal_places=2)
    total_cost = models.DecimalField(max_digits=16, decimal_places=2, editable=False)
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.PROTECT,
        related_name="labour_records",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="production_labour_records",
    )
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductionWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-work_date", "-created_at")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=Q(effort_quantity__gt=0), name="production_labour_effort_positive"),
            models.CheckConstraint(condition=Q(rate__gte=0), name="production_labour_rate_non_negative"),
            models.CheckConstraint(condition=Q(total_cost__gte=0), name="production_labour_total_non_negative"),
        ]


class NurseryActivity(ServiceControlledModel, models.Model):
    class Type(models.TextChoices):
        SEEDING = "SEEDING", "Seeding"
        PRICKING_OUT = "PRICKING_OUT", "Pricking out"
        WATERING = "WATERING", "Watering"
        WEEDING = "WEEDING", "Weeding"
        PEST_MANAGEMENT = "PEST_MANAGEMENT", "Pest management"
        DISEASE_MANAGEMENT = "DISEASE_MANAGEMENT", "Disease management"
        FERTILIZING = "FERTILIZING", "Fertilizing"
        SORTING_GRADING = "SORTING_GRADING", "Sorting or grading"
        CLEANING = "CLEANING", "Cleaning"
        PACKING = "PACKING", "Packing"
        GENERAL = "GENERAL", "General nursery work"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity_date = models.DateField()
    activity_type = models.CharField(max_length=30, choices=Type.choices)
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    description = models.TextField()
    coverage_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    coverage_unit = models.CharField(max_length=50, blank=True)
    person_or_team = models.CharField(max_length=200, blank=True)
    cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="nursery_activities",
    )
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductionWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-activity_date", "-created_at")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=Q(coverage_quantity__isnull=True) | Q(coverage_quantity__gt=0),
                name="nursery_activity_coverage_positive",
            ),
            models.CheckConstraint(
                condition=Q(cost__isnull=True) | Q(cost__gte=0),
                name="nursery_activity_cost_non_negative",
            ),
        ]

    def clean(self):
        super().clean()
        if bool(self.coverage_quantity is not None) != bool(self.coverage_unit.strip()):
            raise ValidationError(
                "Coverage quantity and coverage unit must be supplied together."
            )
