import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ServiceWriteQuerySet(models.QuerySet):
    """Block ORM bulk paths that bypass the authoritative movement service."""

    error_message = "This Inventory record may be changed only by the Inventory movement service."

    def _reject_write(self):
        raise ValidationError(self.error_message)

    def update(self, **kwargs):
        self._reject_write()

    def delete(self):
        self._reject_write()

    def bulk_create(self, objs, **kwargs):
        self._reject_write()

    def bulk_update(self, objs, fields, **kwargs):
        self._reject_write()


class ImmutableMovementQuerySet(ServiceWriteQuerySet):
    error_message = "Posted Inventory movement history is immutable."


class StockPositionQuerySet(ServiceWriteQuerySet):
    error_message = "Stock Positions may be changed only by the Inventory movement service."


class InventorySupply(models.Model):
    class Category(models.TextChoices):
        SEEDS = "SEEDS", "Seeds"
        GROWING_MEDIA = "GROWING_MEDIA", "Growing media"
        NURSERY_TRAYS = "NURSERY_TRAYS", "Nursery trays"
        FERTILIZER = "FERTILIZER", "Fertilizer"
        PESTICIDE = "PESTICIDE", "Pesticide"
        FUNGICIDE = "FUNGICIDE", "Fungicide"
        HERBICIDE = "HERBICIDE", "Herbicide"
        PACKAGING = "PACKAGING", "Packaging"
        NURSERY_SUPPLIES = "NURSERY_SUPPLIES", "Nursery supplies"
        OTHER = "OTHER", "Other operational supply"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=Category.choices)
    base_unit = models.CharField(max_length=50)
    allows_fractional_quantity = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        default_permissions = ()
        permissions = (("manage_supplies", "Can manage Inventory supply definitions"),)
        constraints = [
            models.CheckConstraint(condition=~Q(code=""), name="inventory_supply_code_not_empty"),
            models.CheckConstraint(condition=~Q(name=""), name="inventory_supply_name_not_empty"),
            models.CheckConstraint(condition=~Q(base_unit=""), name="inventory_supply_unit_not_empty"),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        self.name = (self.name or "").strip()
        self.base_unit = (self.base_unit or "").strip().lower()
        errors = {}
        for field in ("code", "name", "base_unit"):
            if not getattr(self, field):
                errors[field] = "This Supply definition field is required."
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and (
                original.code != self.code
                or original.base_unit != self.base_unit
                or original.allows_fractional_quantity != self.allows_fractional_quantity
            ):
                errors["code"] = "Supply code, base unit, and quantity policy are immutable."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not kwargs.pop("_inventory_supply_service_write", False):
            raise ValidationError("Inventory Supply definitions require the Inventory Supply service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory Supply definitions cannot be deleted; deactivate them instead.")

    def __str__(self):
        return f"{self.code} — {self.name}"


class InventorySupplyEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supply = models.ForeignKey(InventorySupply, on_delete=models.PROTECT, related_name="history")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventory_supply_events"
    )
    reason = models.TextField()
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=~Q(reason=""), name="inventory_supply_event_reason_not_empty"),
        ]

    def save(self, *args, **kwargs):
        if not kwargs.pop("_inventory_supply_service_write", False) or not self._state.adding:
            raise ValidationError("Inventory Supply history is append-only service evidence.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory Supply history cannot be deleted.")


class InventoryItem(models.Model):
    class Kind(models.TextChoices):
        PRODUCT = "PRODUCT", "Product"
        SUPPLY = "SUPPLY", "Supply"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(
        "products.Product", on_delete=models.PROTECT, related_name="inventory_item",
        null=True, blank=True,
    )
    supply = models.OneToOneField(
        InventorySupply, on_delete=models.PROTECT, related_name="inventory_item",
        null=True, blank=True,
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PRODUCT)
    base_unit = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind", "product__sku", "supply__code")
        permissions = (
            ("view", "Can view inventory"),
            ("receive", "Can receive inventory"),
            ("release", "Can release inventory"),
            ("adjust", "Can request inventory adjustment"),
            ("approve_adjustment", "Can approve inventory adjustment"),
            ("transfer", "Can transfer inventory"),
        )
        constraints = [
            models.CheckConstraint(
                condition=~Q(base_unit=""), name="inventory_item_base_unit_not_empty"
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="PRODUCT", product__isnull=False, supply__isnull=True)
                    | Q(kind="SUPPLY", product__isnull=True, supply__isnull=False)
                ),
                name="inventory_item_exactly_one_owner",
            ),
        ]

    def clean(self):
        super().clean()
        self.base_unit = (self.base_unit or "").strip()
        if not self.base_unit:
            raise ValidationError({"base_unit": "Inventory base unit is required."})
        if self.kind == self.Kind.PRODUCT and self.product_id and self.base_unit != self.product.base_inventory_unit:
            raise ValidationError({"base_unit": "Inventory base unit must match the Product base unit."})
        if self.kind == self.Kind.SUPPLY and self.supply_id and self.base_unit != self.supply.base_unit:
            raise ValidationError({"base_unit": "Inventory base unit must match the Supply base unit."})
        if self.kind == self.Kind.PRODUCT and (not self.product_id or self.supply_id):
            raise ValidationError("A Product Inventory Item must have only a Product owner.")
        if self.kind == self.Kind.SUPPLY and (not self.supply_id or self.product_id):
            raise ValidationError("A Supply Inventory Item must have only a Supply owner.")
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None:
                is_used = (
                    InventoryMovementLine.objects.filter(item_id=self.pk).exists()
                    or original.commitments.exists()
                )
                if is_used and original.base_unit != self.base_unit:
                    raise ValidationError(
                        {"base_unit": "A used Inventory Item's base unit is immutable."}
                    )
                if is_used and original.product_id != self.product_id:
                    raise ValidationError(
                        {"product": "A used Inventory Item's Product is immutable."}
                    )
                if is_used and (
                    original.kind != self.kind or original.supply_id != self.supply_id
                ):
                    raise ValidationError("A used Inventory Item's kind and owner are immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory Items cannot be deleted; deactivate them instead.")

    def __str__(self):
        code = self.product.sku if self.kind == self.Kind.PRODUCT else self.supply.code
        return f"{code} ({self.base_unit})"


class InventoryLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    allows_saleable_stock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(code=""), name="inventory_location_code_not_empty"
            ),
            models.CheckConstraint(
                condition=~Q(name=""), name="inventory_location_name_not_empty"
            ),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        self.name = (self.name or "").strip()
        errors = {}
        if not self.code:
            errors["code"] = "Location code is required."
        if not self.name:
            errors["name"] = "Location name is required."
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and original.code != self.code:
                errors["code"] = "Inventory Location codes are stable and cannot be changed."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory Locations cannot be deleted; deactivate them instead.")

    def __str__(self):
        return f"{self.code} - {self.name}"


class StockLot(models.Model):
    class Condition(models.TextChoices):
        SALEABLE = "SALEABLE", "Saleable"
        HELD = "HELD", "Held"
        QUARANTINED = "QUARANTINED", "Quarantined"
        DAMAGED = "DAMAGED", "Damaged"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="lots")
    lot_code = models.CharField(max_length=100)
    condition = models.CharField(max_length=12, choices=Condition.choices)
    expiry_date = models.DateField(blank=True, null=True)
    provenance_reference = models.CharField(max_length=160, blank=True)
    provenance_note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("item__product__sku", "lot_code")
        constraints = [
            models.CheckConstraint(condition=~Q(lot_code=""), name="stock_lot_code_not_empty"),
            models.UniqueConstraint(fields=("item", "lot_code"), name="stock_lot_item_code_unique"),
        ]

    def clean(self):
        super().clean()
        self.lot_code = (self.lot_code or "").strip()
        self.provenance_reference = (self.provenance_reference or "").strip()
        self.provenance_note = (self.provenance_note or "").strip()
        if not self.lot_code:
            raise ValidationError({"lot_code": "Lot code is required."})
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and original.condition != self.condition:
                raise ValidationError(
                    {"condition": "Lot condition changes require a future audited condition command."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock Lots cannot be deleted; deactivate them instead.")

    def __str__(self):
        return f"{self.item} lot {self.lot_code}"


class StockPosition(models.Model):
    objects = StockPositionQuerySet.as_manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="positions")
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="stock_positions"
    )
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="positions")
    on_hand_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    version = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("item_id", "location_id", "lot_id")
        constraints = [
            models.UniqueConstraint(
                fields=("item", "location", "lot"),
                name="stock_position_item_location_lot_unique",
            ),
            models.CheckConstraint(
                condition=Q(on_hand_base_quantity__gte=0),
                name="stock_position_on_hand_non_negative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.lot_id and self.item_id and self.lot.item_id != self.item_id:
            raise ValidationError({"lot": "Stock Position lot must belong to its Inventory Item."})

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_inventory_service_write", False)
        if not service_write:
            raise ValidationError("Stock Positions may be changed only by the Inventory movement service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock Positions cannot be deleted.")

    def __str__(self):
        return f"{self.item} at {self.location.code}: {self.on_hand_base_quantity}"


class InventoryMovement(models.Model):
    objects = ImmutableMovementQuerySet.as_manager()

    class Type(models.TextChoices):
        RECEIPT = "RECEIPT", "Receipt"
        ISSUE = "ISSUE", "Issue"
        TRANSFER = "TRANSFER", "Transfer"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment in"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment out"
        REVERSAL = "REVERSAL", "Reversal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_type = models.CharField(max_length=16, choices=Type.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventory_movements"
    )
    reason = models.TextField()
    source_type = models.CharField(max_length=50, blank=True)
    source_reference = models.CharField(max_length=160, blank=True)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    effective_at = models.DateTimeField()
    posted_at = models.DateTimeField(auto_now_add=True)
    reverses = models.OneToOneField(
        "self", on_delete=models.PROTECT, related_name="reversed_by", blank=True, null=True
    )

    class Meta:
        ordering = ("posted_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(reason=""), name="inventory_movement_reason_not_empty"
            ),
            models.CheckConstraint(
                condition=(
                    Q(source_type="", source_reference="")
                    | (~Q(source_type="") & ~Q(source_reference=""))
                ),
                name="inventory_movement_source_both_or_neither",
            ),
            models.CheckConstraint(
                condition=(
                    Q(movement_type="REVERSAL", reverses__isnull=False)
                    | (~Q(movement_type="REVERSAL") & Q(reverses__isnull=True))
                ),
                name="inventory_movement_reversal_reference_consistent",
            ),
            models.UniqueConstraint(
                fields=("source_type", "source_reference"),
                condition=~Q(source_type="") & ~Q(source_reference=""),
                name="inventory_movement_source_reference_unique",
            ),
        ]

    def clean(self):
        super().clean()
        self.reason = (self.reason or "").strip()
        self.source_type = (self.source_type or "").strip()
        self.source_reference = (self.source_reference or "").strip()
        errors = {}
        if not self.reason:
            errors["reason"] = "Movement reason is required."
        if bool(self.source_type) != bool(self.source_reference):
            errors["source_reference"] = "Source type and reference must be supplied together."
        if self.movement_type == self.Type.REVERSAL and not self.reverses_id:
            errors["reverses"] = "A reversal must identify the movement it reverses."
        if self.movement_type != self.Type.REVERSAL and self.reverses_id:
            errors["reverses"] = "Only a reversal may reference a reversed movement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_inventory_service_write", False)
        if not service_write:
            raise ValidationError("Inventory Movements may be created only by the movement service.")
        if not self._state.adding:
            raise ValidationError("Posted Inventory Movements are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted Inventory Movements cannot be deleted.")

    def __str__(self):
        return f"{self.movement_type} {self.id}"


class InventoryMovementLine(models.Model):
    objects = ImmutableMovementQuerySet.as_manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement = models.ForeignKey(
        InventoryMovement, on_delete=models.PROTECT, related_name="lines"
    )
    line_number = models.PositiveIntegerField()
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movement_lines")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="movement_lines")
    quantity = models.DecimalField(max_digits=32, decimal_places=3)
    source_location = models.ForeignKey(
        InventoryLocation,
        on_delete=models.PROTECT,
        related_name="outgoing_movement_lines",
        blank=True,
        null=True,
    )
    destination_location = models.ForeignKey(
        InventoryLocation,
        on_delete=models.PROTECT,
        related_name="incoming_movement_lines",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("line_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("movement", "line_number"),
                name="inventory_movement_line_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(line_number__gt=0), name="inventory_movement_line_number_positive"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="inventory_movement_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(source_location__isnull=False)
                | Q(destination_location__isnull=False),
                name="inventory_movement_line_has_endpoint",
            ),
            models.CheckConstraint(
                condition=Q(source_location__isnull=True)
                | Q(destination_location__isnull=True)
                | ~Q(source_location=models.F("destination_location")),
                name="inventory_movement_line_locations_differ",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.lot_id and self.item_id and self.lot.item_id != self.item_id:
            errors["lot"] = "Movement lot must belong to its Inventory Item."
        if self.source_location_id is None and self.destination_location_id is None:
            errors["destination_location"] = "A movement line requires a source or destination."
        if self.source_location_id and self.source_location_id == self.destination_location_id:
            errors["destination_location"] = "Source and destination locations must differ."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_inventory_service_write", False)
        if not service_write:
            raise ValidationError("Inventory Movement Lines may be created only by the movement service.")
        if not self._state.adding:
            raise ValidationError("Posted Inventory Movement Lines are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted Inventory Movement Lines cannot be deleted.")

    def __str__(self):
        return f"{self.movement_id} line {self.line_number}"


class Reservation(models.Model):
    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CONSUMED = "CONSUMED", "Consumed"
        RELEASED = "RELEASED", "Released"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commitment = models.OneToOneField(
        "commitments.Commitment",
        on_delete=models.PROTECT,
        related_name="reservation",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    initial_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    consumed_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    released_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    remaining_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    state = models.CharField(max_length=8, choices=State.choices, default=State.ACTIVE)
    creation_correlation_id = models.UUIDField(editable=False)
    creation_idempotency_key = models.UUIDField(editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StockPositionQuerySet.as_manager()

    class Meta:
        ordering = ("commitment__confirmed_at", "commitment__fifo_sequence")
        constraints = [
            models.CheckConstraint(
                condition=Q(initial_base_quantity__gt=0),
                name="reservation_initial_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(consumed_base_quantity__gte=0),
                name="reservation_consumed_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(released_base_quantity__gte=0),
                name="reservation_released_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(remaining_base_quantity__gte=0),
                name="reservation_remaining_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(
                    initial_base_quantity=(
                        models.F("consumed_base_quantity")
                        + models.F("released_base_quantity")
                        + models.F("remaining_base_quantity")
                    )
                ),
                name="reservation_quantity_equation",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="ACTIVE", remaining_base_quantity__gt=0)
                    | Q(
                        state="CONSUMED",
                        remaining_base_quantity=0,
                        released_base_quantity=0,
                    )
                    | Q(
                        state="RELEASED",
                        remaining_base_quantity=0,
                        released_base_quantity__gt=0,
                    )
                ),
                name="reservation_state_quantity_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.commitment_id:
            if self.commitment.order_line.supply_mode != "READY":
                errors["commitment"] = "Only READY Commitments may have physical Reservations."
            if self.inventory_item_id != self.commitment.inventory_item_id:
                errors["inventory_item"] = (
                    "Reservation Inventory Item must match its Commitment."
                )
            if self.initial_base_quantity != self.commitment.committed_base_quantity:
                errors["initial_base_quantity"] = (
                    "Reservation quantity must equal the Commitment base quantity."
                )
            if (
                self._state.adding
                and self.commitment.order.status == "PENDING"
                and not getattr(self, "_confirmation_order_locked", False)
            ):
                errors["commitment"] = "PENDING Orders cannot create Reservations."
        if self._state.adding and (
            self.state != self.State.ACTIVE
            or self.consumed_base_quantity != 0
            or self.released_base_quantity != 0
            or self.remaining_base_quantity != self.initial_base_quantity
        ):
            errors["state"] = "A Reservation must begin ACTIVE and wholly remaining."
        if not self._state.adding:
            original = type(self).objects.filter(pk=self.pk).first()
            immutable_fields = (
                "commitment_id",
                "inventory_item_id",
                "initial_base_quantity",
                "creation_correlation_id",
                "creation_idempotency_key",
                "created_at",
            )
            if original is None or any(
                getattr(self, field) != getattr(original, field)
                for field in immutable_fields
            ):
                errors["id"] = "Reservation identity and initial quantity are immutable."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_reservation_service_write", False)
        confirmation_order_locked = kwargs.pop("_confirmation_order_locked", False)
        if not service_write:
            raise ValidationError("Reservations require the Reservation service.")
        self._confirmation_order_locked = confirmation_order_locked
        try:
            self.full_clean()
            return super().save(*args, **kwargs)
        finally:
            del self._confirmation_order_locked

    def delete(self, *args, **kwargs):
        raise ValidationError("Reservations cannot be deleted.")

    def __str__(self):
        return f"Reservation {self.id} for {self.commitment.id}"


class ReservationEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        CONSUMED = "CONSUMED", "Consumed"
        RELEASED = "RELEASED", "Released"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        related_name="events",
    )
    action = models.CharField(max_length=8, choices=Action.choices)
    previous_state = models.CharField(
        max_length=8, choices=Reservation.State.choices, blank=True, null=True
    )
    new_state = models.CharField(max_length=8, choices=Reservation.State.choices)
    base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservation_events",
    )
    reason = models.TextField()
    source_type = models.CharField(max_length=50)
    source_reference = models.CharField(max_length=160)
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableMovementQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("reservation",),
                condition=Q(action="CREATED"),
                name="reservation_one_created_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(action="CREATED", previous_state__isnull=True, new_state="ACTIVE")
                    | Q(
                        action="CONSUMED",
                        previous_state="ACTIVE",
                        new_state__in=("ACTIVE", "CONSUMED"),
                    )
                    | Q(action="RELEASED", previous_state="ACTIVE", new_state="RELEASED")
                ),
                name="reservation_event_valid_transition",
            ),
            models.CheckConstraint(
                condition=Q(base_quantity__gt=0),
                name="reservation_event_quantity_positive",
            ),
            models.CheckConstraint(
                condition=~Q(reason=""), name="reservation_event_reason_not_empty"
            ),
            models.CheckConstraint(
                condition=~Q(source_type=""),
                name="reservation_event_source_type_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(source_reference=""),
                name="reservation_event_source_ref_not_empty",
            ),
        ]

    def clean(self):
        super().clean()
        self.reason = (self.reason or "").strip()
        self.source_type = (self.source_type or "").strip()
        self.source_reference = (self.source_reference or "").strip()
        if not self.reason or not self.source_type or not self.source_reference:
            raise ValidationError("Reservation audit reason and source are required.")
        if self.reservation_id and self.action == self.Action.CREATED and (
            self.base_quantity != self.reservation.initial_base_quantity
            or self.correlation_id != self.reservation.creation_correlation_id
            or self.idempotency_key != self.reservation.creation_idempotency_key
        ):
            raise ValidationError(
                "Initial Reservation event must match its Reservation creation facts."
            )

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_reservation_service_write", False)
        if not service_write or not self._state.adding:
            raise ValidationError("Reservation events are append-only service records.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Reservation events cannot be deleted.")


class SourceAllocationOperation(models.Model):
    class Kind(models.TextChoices):
        INITIAL = "INITIAL", "Initial allocation"
        REALLOCATION = "REALLOCATION", "Reallocation"
        CONSUMPTION = "CONSUMPTION", "Supply consumption"
        RELEASE = "RELEASE", "Cancellation release"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        related_name="allocation_operations",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="source_allocation_operations",
    )
    reason = models.TextField()
    source_type = models.CharField(max_length=50)
    source_reference = models.CharField(max_length=160)
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(editable=False, unique=True)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableMovementQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("reservation",),
                condition=Q(kind="INITIAL"),
                name="allocation_one_initial_operation",
            ),
            models.CheckConstraint(
                condition=~Q(reason=""), name="allocation_operation_reason_not_empty"
            ),
            models.CheckConstraint(
                condition=~Q(source_type=""),
                name="allocation_operation_source_type_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(source_reference=""),
                name="allocation_operation_source_ref_not_empty",
            ),
        ]

    def clean(self):
        super().clean()
        self.reason = (self.reason or "").strip()
        self.source_type = (self.source_type or "").strip()
        self.source_reference = (self.source_reference or "").strip()
        if not self.reason or not self.source_type or not self.source_reference:
            raise ValidationError("Allocation audit reason and source are required.")
        if self.reservation_id and self.kind == self.Kind.INITIAL and (
            self.correlation_id != self.reservation.creation_correlation_id
            or self.idempotency_key != self.reservation.creation_idempotency_key
        ):
            raise ValidationError(
                "Initial Allocation operation must match its Reservation creation identity."
            )

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_reservation_service_write", False)
        if not service_write or not self._state.adding:
            raise ValidationError("Allocation operations are immutable service records.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Allocation operations cannot be deleted.")


class SourceAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    operation = models.ForeignKey(
        SourceAllocationOperation,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    stock_position = models.ForeignKey(
        StockPosition,
        on_delete=models.PROTECT,
        related_name="source_allocations",
    )
    line_number = models.PositiveIntegerField()
    initial_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    consumed_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    released_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    remaining_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    released_by_operation = models.ForeignKey(
        SourceAllocationOperation,
        on_delete=models.PROTECT,
        related_name="released_allocations",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StockPositionQuerySet.as_manager()

    class Meta:
        ordering = ("operation__created_at", "line_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("operation", "line_number"),
                name="source_allocation_operation_line_unique",
            ),
            models.UniqueConstraint(
                fields=("reservation", "stock_position"),
                condition=Q(remaining_base_quantity__gt=0),
                name="source_allocation_active_position_unique",
            ),
            models.CheckConstraint(
                condition=Q(line_number__gt=0),
                name="source_allocation_line_positive",
            ),
            models.CheckConstraint(
                condition=Q(initial_base_quantity__gt=0),
                name="source_allocation_initial_positive",
            ),
            models.CheckConstraint(
                condition=Q(consumed_base_quantity__gte=0),
                name="source_allocation_consumed_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(released_base_quantity__gte=0),
                name="source_allocation_released_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(remaining_base_quantity__gte=0),
                name="source_allocation_remaining_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(
                    initial_base_quantity=(
                        models.F("consumed_base_quantity")
                        + models.F("released_base_quantity")
                        + models.F("remaining_base_quantity")
                    )
                ),
                name="source_allocation_quantity_equation",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.operation_id and self.reservation_id:
            if self.operation.reservation_id != self.reservation_id:
                errors["operation"] = "Allocation operation must belong to its Reservation."
        if self.stock_position_id and self.reservation_id:
            if self.stock_position.item_id != self.reservation.inventory_item_id:
                errors["stock_position"] = (
                    "Allocation Position must match the Reservation Inventory Item."
                )
        if self._state.adding and (
            self.consumed_base_quantity != 0
            or self.released_base_quantity != 0
            or self.remaining_base_quantity != self.initial_base_quantity
            or self.released_by_operation_id is not None
        ):
            errors["remaining_base_quantity"] = (
                "A Source Allocation must begin wholly remaining."
            )
        if not self._state.adding:
            original = type(self).objects.filter(pk=self.pk).first()
            immutable_fields = (
                "reservation_id",
                "operation_id",
                "stock_position_id",
                "line_number",
                "initial_base_quantity",
                "created_at",
            )
            if original is None or any(
                getattr(self, field) != getattr(original, field)
                for field in immutable_fields
            ):
                errors["id"] = "Allocation identity, source and initial quantity are immutable."
            if (
                original is not None
                and original.released_by_operation_id is not None
                and self.released_by_operation_id != original.released_by_operation_id
            ):
                errors["released_by_operation"] = "A released Allocation cannot be rewritten."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_reservation_service_write", False)
        if not service_write:
            raise ValidationError("Source Allocations require the Allocation service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Source Allocations cannot be deleted.")

    @property
    def is_active(self):
        return self.remaining_base_quantity > 0

    def __str__(self):
        return f"Allocation {self.id} from {self.stock_position_id}"


class SourceAllocationConsumption(models.Model):
    """Append-only allocation quantity consumed by one supply operation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.ForeignKey(
        SourceAllocationOperation,
        on_delete=models.PROTECT,
        related_name="consumptions",
    )
    allocation = models.ForeignKey(
        SourceAllocation,
        on_delete=models.PROTECT,
        related_name="consumptions",
    )
    supply_event = models.ForeignKey(
        "commitments.CommitmentSupplyEvent",
        on_delete=models.PROTECT,
        related_name="allocation_consumptions",
    )
    line_number = models.PositiveIntegerField()
    base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableMovementQuerySet.as_manager()

    class Meta:
        ordering = ("operation__created_at", "line_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("operation", "line_number"),
                name="allocation_consumption_line_unique",
            ),
            models.UniqueConstraint(
                fields=("operation", "allocation"),
                name="allocation_consumption_source_unique",
            ),
            models.CheckConstraint(
                condition=Q(line_number__gt=0),
                name="allocation_consumption_line_positive",
            ),
            models.CheckConstraint(
                condition=Q(base_quantity__gt=0),
                name="allocation_consumption_quantity_positive",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.operation_id:
            if self.operation.kind != SourceAllocationOperation.Kind.CONSUMPTION:
                errors["operation"] = "Consumption history requires a CONSUMPTION operation."
            if self.allocation_id and self.operation.reservation_id != self.allocation.reservation_id:
                errors["allocation"] = "Consumed Allocation must belong to the operation Reservation."
        if self.supply_event_id and self.allocation_id:
            if self.supply_event.commitment_id != self.allocation.reservation.commitment_id:
                errors["supply_event"] = "Supply Event must belong to the Allocation Commitment."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_reservation_service_write", False)
        if not service_write or not self._state.adding:
            raise ValidationError("Allocation consumption history is append-only service data.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Allocation consumption history cannot be deleted.")


class InventoryAdjustmentRequest(models.Model):
    class Direction(models.TextChoices):
        IN = "IN", "Increase"
        OUT = "OUT", "Decrease"

    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="adjustments")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="adjustments")
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="adjustments"
    )
    direction = models.CharField(max_length=3, choices=Direction.choices)
    base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_inventory_adjustments"
    )
    request_reason = models.TextField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approved_inventory_adjustments",
        null=True, blank=True,
    )
    approval_reason = models.TextField(blank=True)
    movement = models.OneToOneField(
        InventoryMovement, on_delete=models.PROTECT, related_name="adjustment_request",
        null=True, blank=True,
    )
    correlation_id = models.UUIDField(editable=False)
    request_idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    approval_idempotency_key = models.UUIDField(unique=True, editable=False, null=True, blank=True)
    approval_fingerprint = models.CharField(max_length=64, editable=False, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    objects = StockPositionQuerySet.as_manager()

    class Meta:
        ordering = ("-requested_at", "id")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=Q(base_quantity__gt=0), name="inventory_adjustment_quantity_positive"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        state="PENDING", approver__isnull=True, movement__isnull=True,
                        approved_at__isnull=True, approval_idempotency_key__isnull=True,
                        approval_reason="", approval_fingerprint="",
                    )
                    | Q(
                        state="APPROVED", approver__isnull=False, movement__isnull=False,
                        approved_at__isnull=False, approval_idempotency_key__isnull=False,
                    )
                ),
                name="inventory_adjustment_state_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        self.request_reason = (self.request_reason or "").strip()
        self.approval_reason = (self.approval_reason or "").strip()
        errors = {}
        if not self.request_reason:
            errors["request_reason"] = "An adjustment request reason is required."
        if self.lot_id and self.item_id and self.lot.item_id != self.item_id:
            errors["lot"] = "Adjustment lot must belong to its Inventory Item."
        if self.approver_id and self.approver_id == self.requester_id:
            errors["approver"] = "The requester cannot approve their own adjustment."
        if self.state == self.State.APPROVED and not self.approval_reason:
            errors["approval_reason"] = "An approval reason is required."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not kwargs.pop("_inventory_adjustment_service_write", False):
            raise ValidationError("Inventory adjustments require the adjustment service.")
        self.full_clean()
        return models.Model.save(self, *args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory adjustment history cannot be deleted.")
