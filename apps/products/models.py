import uuid

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import Q

from .image_validation import product_image_upload_path, validate_product_image


class Product(models.Model):
    class Category(models.TextChoices):
        VEGETABLE = "VEG", "Vegetable"
        FRUIT = "FRT", "Fruit"
        TREE = "TRE", "Tree"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=3, choices=Category.choices)
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
                condition=Q(category__in=("VEG", "FRT", "TRE")),
                name="product_category_supported",
            ),
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


class ProductImage(models.Model):
    """Customer-facing photographs. The first ordered image is the main image."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_upload_path, max_length=255)
    alt_text = models.CharField(max_length=250, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "created_at", "id")
        default_permissions = ()

    @property
    def display_alt_text(self):
        return self.alt_text or self.product.name

    @property
    def display_url(self):
        if self.image and self.image.storage.exists(self.image.name):
            return self.image.url
        return ""

    def clean(self):
        super().clean()
        self.alt_text = (self.alt_text or "").strip()
        original = type(self).objects.filter(pk=self.pk).first() if not self._state.adding else None
        if original and (original.product_id != self.product_id or original.image.name != self.image.name):
            raise ValidationError("An existing image cannot move Product or replace its stored file. Upload another image instead.")
        if self._state.adding and self.image and self.image._committed:
            raise ValidationError({"image": "Upload a new image file; stored paths cannot be attached directly."})
        if self.image and not self.image._committed:
            validate_product_image(self.image)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} image ({self.sort_order})"


class ProductSkuSequence(models.Model):
    """Service-controlled counter used to allocate Product SKUs safely."""

    category = models.CharField(
        max_length=3,
        choices=Product.Category.choices,
        primary_key=True,
    )
    last_value = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(last_value__gte=0),
                name="product_sku_sequence_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.category}: {self.last_value}"


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
