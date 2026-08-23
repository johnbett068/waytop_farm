import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import Q

from apps.customers.normalization import normalize_email, normalize_kenyan_phone


ORDER_NUMBER_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_order_number():
    token = "".join(secrets.choice(ORDER_NUMBER_ALPHABET) for _ in range(12))
    return f"WTF-{token[:4]}-{token[4:8]}-{token[8:]}"


class ProtectedOrderQuerySet(models.QuerySet):
    def _reject_write(self):
        raise ValidationError("Order facts and history require a controlled domain service.")

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


class Order(models.Model):
    class Channel(models.TextChoices):
        ECOMMERCE = "ECOMMERCE", "Ecommerce"
        POS = "POS", "Point of Sale"

    class FulfillmentMethod(models.TextChoices):
        HOME_DELIVERY = "HOME_DELIVERY", "Home delivery"
        CUSTOMER_COLLECTION = "CUSTOMER_COLLECTION", "Customer collection"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PROCESSING = "PROCESSING", "Processing"
        FULFILLED = "FULFILLED", "Fulfilled"
        CANCELLED = "CANCELLED", "Cancelled"

    class Currency(models.TextChoices):
        KES = "KES", "Kenyan shilling"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=18, unique=True, default=generate_order_number, editable=False)
    creation_idempotency_key = models.UUIDField(unique=True, editable=False)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders", blank=True, null=True
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    fulfillment_method = models.CharField(max_length=20, choices=FulfillmentMethod.choices)
    required_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, editable=False)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.KES, editable=False)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProtectedOrderQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        permissions = (
            ("view", "Can view orders"),
            ("cancel", "Can cancel orders"),
            ("process", "Can start Order processing"),
        )
        constraints = [
            models.CheckConstraint(condition=Q(total_amount__gt=0), name="order_total_positive"),
            models.CheckConstraint(condition=Q(currency="KES"), name="order_currency_kes"),
        ]

    def clean(self):
        super().clean()
        if self._state.adding and self.customer_id and not self.customer.is_active:
            raise ValidationError({"customer": "An inactive customer cannot be attached to a new order."})
        if self._state.adding and self.status != self.Status.PENDING:
            raise ValidationError({"status": "A new order must be pending."})

    def save(self, *args, **kwargs):
        confirmation_write = kwargs.pop("_confirmation_service_write", False)
        processing_write = kwargs.pop("_processing_service_write", False)
        cancellation_write = kwargs.pop("_cancellation_service_write", False)
        fulfillment_write = kwargs.pop("_fulfillment_service_write", False)
        if not self._state.adding:
            original = type(self).objects.only("status").get(pk=self.pk)
            valid_transition = (
                confirmation_write
                and original.status == self.Status.PENDING
                and self.status == self.Status.CONFIRMED
            ) or (
                processing_write
                and original.status == self.Status.CONFIRMED
                and self.status == self.Status.PROCESSING
            ) or (
                cancellation_write
                and original.status in (self.Status.CONFIRMED, self.Status.PROCESSING)
                and self.status == self.Status.CANCELLED
            ) or (
                fulfillment_write
                and original.status == self.Status.PROCESSING
                and self.status == self.Status.FULFILLED
            )
            if not valid_transition:
                raise ValidationError("Order lifecycle changes require the matching domain service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Orders cannot be deleted.")

    def __str__(self):
        return self.order_number


class OrderContactSnapshot(ImmutableRecordMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="contact_snapshot")
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=16, blank=True)
    email = models.EmailField(blank=True)

    objects = ProtectedOrderQuerySet.as_manager()

    def clean(self):
        super().clean()
        self.name = (self.name or "").strip()
        self.phone = normalize_kenyan_phone(self.phone)
        self.email = normalize_email(self.email)
        if self.email:
            validate_email(self.email)

    def __str__(self):
        return f"Contact snapshot for {self.order.order_number}"


class OrderAddressSnapshot(ImmutableRecordMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="address_snapshot")
    county = models.CharField(max_length=100)
    town_or_area = models.CharField(max_length=160)
    address_line = models.CharField(max_length=500)
    delivery_instructions = models.TextField(blank=True)

    objects = ProtectedOrderQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(county=""), name="order_address_county_not_empty"),
            models.CheckConstraint(condition=~Q(town_or_area=""), name="order_address_town_not_empty"),
            models.CheckConstraint(condition=~Q(address_line=""), name="order_address_line_not_empty"),
        ]

    def clean(self):
        super().clean()
        for field in ("county", "town_or_area", "address_line", "delivery_instructions"):
            setattr(self, field, (getattr(self, field) or "").strip())
        errors = {
            field: "This historical address field is required."
            for field in ("county", "town_or_area", "address_line")
            if not getattr(self, field)
        }
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Address snapshot for {self.order.order_number}"


class OrderLine(ImmutableRecordMixin):
    class SupplyMode(models.TextChoices):
        READY = "READY", "Ready"
        PRE_ORDER = "PRE_ORDER", "Pre-order"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveIntegerField()
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="order_lines")
    sale_unit = models.ForeignKey(
        "products.ProductSaleUnit", on_delete=models.PROTECT, related_name="order_lines"
    )
    source_price = models.ForeignKey(
        "products.ProductPrice", on_delete=models.PROTECT, related_name="order_lines"
    )
    product_sku = models.CharField(max_length=64)
    product_name = models.CharField(max_length=200)
    sale_unit_name = models.CharField(max_length=100)
    base_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    quantity = models.PositiveBigIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=18, decimal_places=2)
    supply_mode = models.CharField(max_length=10, choices=SupplyMode.choices)
    confirmed_quantity = models.PositiveBigIntegerField(default=0)
    outstanding_quantity = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedOrderQuerySet.as_manager()

    class Meta:
        ordering = ("line_number",)
        constraints = [
            models.UniqueConstraint(fields=("order", "line_number"), name="order_line_number_unique"),
            models.CheckConstraint(condition=Q(line_number__gt=0), name="order_line_number_positive"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="order_line_quantity_positive"),
            models.CheckConstraint(condition=Q(base_quantity__gt=0), name="order_line_base_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="order_line_unit_price_non_negative"),
            models.CheckConstraint(condition=Q(line_total__gte=0), name="order_line_total_non_negative"),
            models.CheckConstraint(
                condition=Q(confirmed_quantity__lte=models.F("quantity")),
                name="order_line_confirmed_lte_ordered",
            ),
            models.CheckConstraint(
                condition=Q(outstanding_quantity__lte=models.F("confirmed_quantity")),
                name="order_line_outstanding_lte_confirmed",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.sale_unit_id and self.product_id and self.sale_unit.product_id != self.product_id:
            errors["sale_unit"] = "The sale unit must belong to the selected product."
        if self.source_price_id and self.sale_unit_id and self.source_price.sale_unit_id != self.sale_unit_id:
            errors["source_price"] = "The source price must belong to the selected sale unit."
        if self.line_total != self.quantity * self.unit_price:
            errors["line_total"] = "Line total must equal quantity multiplied by unit price."
        if self._state.adding and (self.confirmed_quantity or self.outstanding_quantity):
            errors["confirmed_quantity"] = (
                "Pending Order Lines cannot contain confirmed or outstanding commitments."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.order.order_number} line {self.line_number}"

    def save(self, *args, **kwargs):
        confirmation_write = kwargs.pop("_confirmation_service_write", False)
        supply_write = kwargs.pop("_supply_service_write", False)
        cancellation_write = kwargs.pop("_cancellation_service_write", False)
        if not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "order_id", "line_number", "product_id", "sale_unit_id", "source_price_id",
                "product_sku", "product_name", "sale_unit_name", "base_quantity", "quantity",
                "unit_price", "line_total", "supply_mode", "created_at",
            )
            if any(getattr(self, field) != getattr(original, field) for field in immutable_fields):
                raise ValidationError("Order Line commercial snapshots are immutable.")
            valid_counters = (
                confirmation_write
                and original.confirmed_quantity == 0
                and original.outstanding_quantity == 0
                and self.confirmed_quantity == self.quantity
                and self.outstanding_quantity == self.quantity
            ) or (
                supply_write
                and self.confirmed_quantity == original.confirmed_quantity
                and 0 <= self.outstanding_quantity < original.outstanding_quantity
            ) or (
                cancellation_write
                and self.confirmed_quantity == original.confirmed_quantity
                and self.outstanding_quantity == 0
                and original.outstanding_quantity >= 0
            )
            if not valid_counters:
                raise ValidationError("Order Line quantities require the matching domain service.")
        self.full_clean()
        return models.Model.save(self, *args, **kwargs)


class OrderStatusEvent(ImmutableRecordMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="status_events")
    previous_status = models.CharField(
        max_length=12, choices=Order.Status.choices, blank=True, null=True
    )
    new_status = models.CharField(max_length=12, choices=Order.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="order_status_events",
        blank=True,
        null=True,
    )
    reason = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProtectedOrderQuerySet.as_manager()

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("order",),
                condition=Q(previous_status__isnull=True),
                name="order_one_initial_status_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(previous_status__isnull=True, new_status="PENDING")
                    | Q(
                        previous_status="PENDING",
                        new_status="CONFIRMED",
                        actor__isnull=False,
                    )
                    | (
                        Q(
                            previous_status="CONFIRMED",
                            new_status="PROCESSING",
                            actor__isnull=False,
                        )
                        & ~Q(reason="")
                    )
                    | (
                        Q(
                            previous_status__in=("CONFIRMED", "PROCESSING"),
                            new_status="CANCELLED",
                            actor__isnull=False,
                        )
                        & ~Q(reason="")
                    )
                    | Q(
                        previous_status="PROCESSING",
                        new_status="FULFILLED",
                        actor__isnull=False,
                    )
                ),
                name="order_status_event_valid_transition",
            ),
        ]

    def clean(self):
        super().clean()
        creation_transition = (
            getattr(self, "_creation_service_write", False)
            and self.previous_status is None
            and self.new_status == Order.Status.PENDING
        )
        confirmation_transition = (
            getattr(self, "_confirmation_service_write", False)
            and self.previous_status == Order.Status.PENDING
            and self.new_status == Order.Status.CONFIRMED
            and self.actor_id is not None
        )
        processing_transition = (
            getattr(self, "_processing_service_write", False)
            and self.previous_status == Order.Status.CONFIRMED
            and self.new_status == Order.Status.PROCESSING
            and self.actor_id is not None
            and bool((self.reason or "").strip())
        )
        cancellation_transition = (
            getattr(self, "_cancellation_service_write", False)
            and self.previous_status in (Order.Status.CONFIRMED, Order.Status.PROCESSING)
            and self.new_status == Order.Status.CANCELLED
            and self.actor_id is not None
            and bool((self.reason or "").strip())
        )
        fulfillment_transition = (
            getattr(self, "_fulfillment_service_write", False)
            and self.previous_status == Order.Status.PROCESSING
            and self.new_status == Order.Status.FULFILLED
            and self.actor_id is not None
        )
        if not (
            creation_transition
            or confirmation_transition
            or processing_transition
            or cancellation_transition
            or fulfillment_transition
        ):
            raise ValidationError(
                "Order status transitions require their matching domain service."
            )

    def save(self, *args, **kwargs):
        creation_write = kwargs.pop("_creation_service_write", False)
        confirmation_write = kwargs.pop("_confirmation_service_write", False)
        processing_write = kwargs.pop("_processing_service_write", False)
        cancellation_write = kwargs.pop("_cancellation_service_write", False)
        fulfillment_write = kwargs.pop("_fulfillment_service_write", False)
        if not self._state.adding:
            raise ValidationError("Order status events are immutable.")
        self._creation_service_write = creation_write
        self._confirmation_service_write = confirmation_write
        self._processing_service_write = processing_write
        self._cancellation_service_write = cancellation_write
        self._fulfillment_service_write = fulfillment_write
        try:
            self.full_clean()
            return models.Model.save(self, *args, **kwargs)
        finally:
            del self._creation_service_write
            del self._confirmation_service_write
            del self._processing_service_write
            del self._cancellation_service_write
            del self._fulfillment_service_write

    def __str__(self):
        return f"{self.order.order_number}: {self.new_status}"
