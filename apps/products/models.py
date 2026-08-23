import uuid

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import Q


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    base_inventory_unit = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "sku")
        constraints = [
            models.CheckConstraint(
                condition=Q(is_active=True) | Q(is_published=False),
                name="product_published_requires_active",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_published and not self.is_active:
            raise ValidationError({"is_published": "An inactive product cannot be published."})
        if not self.pk:
            return
        original = type(self).objects.filter(pk=self.pk).first()
        if original is None or original.base_inventory_unit == self.base_inventory_unit:
            return
        try:
            inventory_item = self.inventory_item
        except ObjectDoesNotExist:
            inventory_item = None
        if inventory_item is not None and (
            inventory_item.movement_lines.exists() or inventory_item.commitments.exists()
        ):
            raise ValidationError(
                {
                    "base_inventory_unit":
                        "A Product base unit is immutable after Inventory use."
                }
            )

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and original.base_inventory_unit != self.base_inventory_unit:
                try:
                    inventory_item = self.inventory_item
                except ObjectDoesNotExist:
                    inventory_item = None
                if inventory_item is not None and (
                    inventory_item.movement_lines.exists()
                    or inventory_item.commitments.exists()
                ):
                    raise ValidationError(
                        {
                            "base_inventory_unit":
                                "A Product base unit is immutable after Inventory use."
                        }
                    )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} — {self.name}"


class ProductSaleUnit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_units")
    name = models.CharField(max_length=100)
    base_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("base_quantity", "name")
        constraints = [
            models.CheckConstraint(
                condition=Q(base_quantity__gt=0),
                name="product_sale_unit_positive_quantity",
            ),
            models.UniqueConstraint(
                fields=("product", "name"),
                name="product_sale_unit_unique_name",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.name}"


class ProductPrice(models.Model):
    class Currency(models.TextChoices):
        KES = "KES", "Kenyan shilling"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale_unit = models.ForeignKey(ProductSaleUnit, on_delete=models.PROTECT, related_name="prices")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.KES)
    effective_start = models.DateTimeField()
    effective_end = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-effective_start", "-created_at")
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="product_price_non_negative"),
            models.CheckConstraint(condition=Q(currency="KES"), name="product_price_currency_supported"),
            models.CheckConstraint(
                condition=Q(effective_end__isnull=True) | Q(effective_end__gt=models.F("effective_start")),
                name="product_price_valid_period",
            ),
            models.UniqueConstraint(
                fields=("sale_unit", "effective_start"),
                name="product_price_unique_start",
            ),
        ]

    def clean(self):
        super().clean()
        if self.effective_end is not None and self.effective_end <= self.effective_start:
            raise ValidationError({"effective_end": "Effective end must be later than effective start."})
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None:
                immutable_fields = ("sale_unit_id", "amount", "currency", "effective_start")
                changed = [field for field in immutable_fields if getattr(self, field) != getattr(original, field)]
                if changed:
                    raise ValidationError(
                        "An existing price's sale unit, amount, currency, and start cannot be changed; create a new price version."
                    )
                if original.effective_end is not None and self.effective_end != original.effective_end:
                    raise ValidationError(
                        {"effective_end": "A closed price period cannot be reopened or rewritten."}
                    )
        if not self.is_active or not self.sale_unit_id or not self.effective_start:
            return

        overlaps = type(self).objects.filter(sale_unit_id=self.sale_unit_id, is_active=True).exclude(pk=self.pk)
        if self.effective_end is not None:
            overlaps = overlaps.filter(effective_start__lt=self.effective_end)
        overlaps = overlaps.filter(Q(effective_end__isnull=True) | Q(effective_end__gt=self.effective_start))
        if overlaps.exists():
            raise ValidationError("Active price periods for a sale unit must not overlap.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.sale_unit_id:
                ProductSaleUnit.objects.select_for_update().get(pk=self.sale_unit_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale_unit} — {self.currency} {self.amount}"
