import uuid
from decimal import Decimal, ROUND_HALF_EVEN

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class ProcurementWriteQuerySet(models.QuerySet):
    def _reject(self):
        raise ValidationError("Procurement records require a controlled domain service.")

    def update(self, **kwargs): self._reject()
    def delete(self): self._reject()
    def bulk_create(self, objs, **kwargs): self._reject()
    def bulk_update(self, objs, fields, **kwargs): self._reject()


class ServiceControlledModel:
    def save(self, *args, **kwargs):
        if not kwargs.pop("_procurement_service_write", False):
            raise ValidationError("Procurement records require a controlled domain service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Procurement records cannot be deleted.")


class ImmutableServiceControlledModel(ServiceControlledModel):
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(f"{type(self).__name__} history is immutable.")
        return super().save(*args, **kwargs)


class Supplier(ServiceControlledModel, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("code",)
        default_permissions = ()
        permissions = (
            ("view", "Can view Supplier procurement"),
            ("manage_suppliers", "Can manage Suppliers"),
            ("manage_purchases", "Can manage Supplier purchases"),
        )
        constraints = [
            models.CheckConstraint(condition=~Q(code=""), name="supplier_code_not_empty"),
            models.CheckConstraint(condition=~Q(name=""), name="supplier_name_not_empty"),
        ]

    def clean(self):
        super().clean()
        for field in ("code", "name", "contact_person", "phone", "email", "address", "notes"):
            value = (getattr(self, field) or "").strip()
            setattr(self, field, value.upper() if field == "code" else value)
        if not self.code or not self.name:
            raise ValidationError("Supplier code and name are required.")
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and original.code != self.code:
                raise ValidationError({"code": "Supplier code is immutable."})

    def __str__(self): return f"{self.code} — {self.name}"


class SupplierEvent(ImmutableServiceControlledModel, models.Model):
    class Operation(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        DEACTIVATED = "DEACTIVATED", "Deactivated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="history")
    operation = models.CharField(max_length=20, choices=Operation.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        default_permissions = ()


class SupplierPurchaseOrder(ServiceControlledModel, models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ORDERED = "ORDERED", "Ordered"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially received"
        RECEIVED = "RECEIVED", "Received"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=64, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    order_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    currency = models.CharField(max_length=3, default="KES", editable=False)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-order_date", "number")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=Q(currency="KES"), name="supplier_po_currency_kes"),
            models.CheckConstraint(
                condition=Q(expected_date__isnull=True) | Q(expected_date__gte=F("order_date")),
                name="supplier_po_dates_ordered",
            ),
        ]

    def clean(self):
        super().clean()
        self.number = (self.number or "").strip().upper()
        self.reference = (self.reference or "").strip()
        self.notes = (self.notes or "").strip()
        if not self.number: raise ValidationError({"number": "Purchase Order number is required."})
        if self._state.adding and self.supplier_id and not self.supplier.is_active:
            raise ValidationError({"supplier": "An inactive Supplier cannot receive a new order."})
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and (
                original.number != self.number or original.supplier_id != self.supplier_id
                or original.order_date != self.order_date or original.currency != self.currency
            ):
                raise ValidationError("Purchase Order identity and commercial header are immutable.")

    def __str__(self): return self.number


class SupplierPurchaseOrderLine(ServiceControlledModel, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(SupplierPurchaseOrder, on_delete=models.PROTECT, related_name="lines")
    line_number = models.PositiveIntegerField()
    supply = models.ForeignKey("inventory.InventorySupply", on_delete=models.PROTECT, related_name="purchase_lines")
    supply_code = models.CharField(max_length=64)
    supply_name = models.CharField(max_length=200)
    purchase_unit = models.CharField(max_length=50)
    ordered_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    base_quantity_per_purchase_unit = models.DecimalField(max_digits=32, decimal_places=3)
    ordered_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    received_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    rejected_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=18, decimal_places=2)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("line_number",)
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("purchase_order", "line_number"), name="supplier_po_line_unique"),
            models.CheckConstraint(condition=Q(ordered_quantity__gt=0), name="supplier_po_ordered_quantity_positive"),
            models.CheckConstraint(condition=Q(base_quantity_per_purchase_unit__gt=0), name="supplier_po_conversion_positive"),
            models.CheckConstraint(condition=Q(ordered_base_quantity__gt=0), name="supplier_po_ordered_base_positive"),
            models.CheckConstraint(condition=Q(received_base_quantity__gte=0), name="supplier_po_received_non_negative"),
            models.CheckConstraint(condition=Q(rejected_base_quantity__gte=0), name="supplier_po_rejected_non_negative"),
            models.CheckConstraint(condition=Q(received_base_quantity__lte=F("ordered_base_quantity")), name="supplier_po_received_not_above_ordered"),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="supplier_po_unit_cost_non_negative"),
            models.CheckConstraint(condition=Q(line_total__gte=0), name="supplier_po_line_total_non_negative"),
        ]

    def clean(self):
        super().clean()
        expected_base = self.ordered_quantity * self.base_quantity_per_purchase_unit
        if expected_base != expected_base.quantize(Decimal("0.001")) or self.ordered_base_quantity != expected_base:
            raise ValidationError({"ordered_base_quantity": "Ordered base quantity must match the deterministic conversion."})
        expected_total = (self.ordered_quantity * self.unit_cost).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        if self.line_total != expected_total:
            raise ValidationError({"line_total": "Line total must equal ordered quantity multiplied by unit cost."})
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            immutable = (
                "purchase_order_id", "line_number", "supply_id", "supply_code", "supply_name",
                "purchase_unit", "ordered_quantity", "base_quantity_per_purchase_unit",
                "ordered_base_quantity", "unit_cost", "line_total",
            )
            if original is not None and any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError("Purchase Order line snapshots are immutable.")

    @property
    def outstanding_base_quantity(self):
        return self.ordered_base_quantity - self.received_base_quantity

    def __str__(self):
        return (
            f"{self.purchase_order.number} — {self.supply_name}: "
            f"{self.outstanding_base_quantity} {self.supply.base_unit} outstanding "
            f"({self.ordered_quantity} {self.purchase_unit} ordered)"
        )


class PurchaseOrderEvent(ImmutableServiceControlledModel, models.Model):
    class Operation(models.TextChoices):
        CREATED = "CREATED", "Created"
        PLACED = "PLACED", "Placed"
        CANCELLED = "CANCELLED", "Cancelled"
        RECEIPT_POSTED = "RECEIPT_POSTED", "Receipt posted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(SupplierPurchaseOrder, on_delete=models.PROTECT, related_name="history")
    operation = models.CharField(max_length=20, choices=Operation.choices)
    previous_status = models.CharField(max_length=20, choices=SupplierPurchaseOrder.Status.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=SupplierPurchaseOrder.Status.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        default_permissions = ()


class SupplierGoodsReceipt(ImmutableServiceControlledModel, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=64, unique=True)
    purchase_order = models.ForeignKey(SupplierPurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts")
    delivery_note_reference = models.CharField(max_length=160)
    receipt_date = models.DateField()
    movement = models.OneToOneField("inventory.InventoryMovement", on_delete=models.PROTECT, related_name="supplier_goods_receipt")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("-receipt_date", "number")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=~Q(number=""), name="goods_receipt_number_not_empty"),
            models.CheckConstraint(condition=~Q(delivery_note_reference=""), name="goods_receipt_delivery_note_not_empty"),
            models.CheckConstraint(condition=~Q(reason=""), name="goods_receipt_reason_not_empty"),
        ]


class GoodsReceiptLine(ImmutableServiceControlledModel, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(SupplierGoodsReceipt, on_delete=models.PROTECT, related_name="lines")
    line_number = models.PositiveIntegerField()
    purchase_order_line = models.ForeignKey(SupplierPurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines")
    movement_line = models.OneToOneField("inventory.InventoryMovementLine", on_delete=models.PROTECT, null=True, blank=True)
    stock_lot = models.ForeignKey("inventory.StockLot", on_delete=models.PROTECT)
    destination_location = models.ForeignKey("inventory.InventoryLocation", on_delete=models.PROTECT)
    accepted_base_quantity = models.DecimalField(max_digits=32, decimal_places=3)
    rejected_base_quantity = models.DecimalField(max_digits=32, decimal_places=3, default=0)
    rejection_reason = models.TextField(blank=True)

    objects = ProcurementWriteQuerySet.as_manager()

    class Meta:
        ordering = ("line_number",)
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("receipt", "line_number"), name="goods_receipt_line_unique"),
            models.CheckConstraint(condition=Q(accepted_base_quantity__gte=0), name="goods_receipt_accepted_non_negative"),
            models.CheckConstraint(condition=Q(rejected_base_quantity__gte=0), name="goods_receipt_rejected_non_negative"),
            models.CheckConstraint(condition=Q(accepted_base_quantity__gt=0) | Q(rejected_base_quantity__gt=0), name="goods_receipt_line_has_quantity"),
        ]

    def clean(self):
        super().clean()
        self.rejection_reason = (self.rejection_reason or "").strip()
        if self.rejected_base_quantity > 0 and not self.rejection_reason:
            raise ValidationError({"rejection_reason": "Rejected quantity requires a reason."})
        if self.accepted_base_quantity > 0 and not self.movement_line_id:
            raise ValidationError({"movement_line": "Accepted quantity requires an Inventory Movement Line."})
