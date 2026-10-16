from django import forms
from django.utils import timezone

from .models import Product, ProductSaleUnit
from .image_validation import MAX_IMAGE_BYTES, validate_product_image


class ProductImageMetadataForm(forms.Form):
    alt_text = forms.CharField(max_length=250, required=False, label="Alt text",
                               help_text="Describe the photograph for accessibility. Blank uses the Product name.")
    sort_order = forms.IntegerField(min_value=0, max_value=2147483647, initial=0, label="Display order",
                                    help_text="Lower numbers appear first. The first image is the main image.")


class ProductImageUploadForm(ProductImageMetadataForm):
    max_image_bytes = MAX_IMAGE_BYTES
    max_image_mib = MAX_IMAGE_BYTES / (1024 * 1024)
    image = forms.ImageField(validators=[validate_product_image], label="Image",
                             help_text="Use a valid JPG/JPEG, PNG, WebP or GIF file with its matching extension.",
                             widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp,image/gif"}))


class ProductFirstImageForm(ProductImageUploadForm):
    """Reuse upload validation; creation needs only an optional first image."""
    sort_order = None
    field_order = ("image", "alt_text")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False


class StaffProductCreateForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        label="Product name",
        help_text="Use the seedling name customers and nursery staff recognize.",
    )
    category = forms.ChoiceField(
        choices=Product.Category.choices,
        label="Product category",
        help_text="Used to generate the Product SKU automatically.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="A truthful description of the seedling sold by WayTop Farm.",
    )
    base_inventory_unit = forms.CharField(
        max_length=50,
        label="Stock unit",
        initial="seedling",
        help_text="The smallest counted unit, usually seedling.",
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Active product",
        help_text="Active Products can be selected for new Production batches.",
    )
    is_published = forms.BooleanField(
        required=False,
        initial=False,
        label="Show in public catalog",
        help_text="Published Products must also be active.",
    )
    sale_unit_name = forms.CharField(
        max_length=100,
        initial="Individual seedling",
        label="Sale unit",
        help_text="How the Product is sold, such as Individual seedling or Tray of 128.",
    )
    sale_unit_base_quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=0.001,
        initial="1.000",
        label="Seedlings per sale unit",
        help_text="How many base units are contained in one sale unit.",
    )
    price_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        label="Price (KES)",
        help_text="Optional. Leave blank if the commercial price is not yet approved.",
    )
    price_effective_start = forms.DateTimeField(
        required=False,
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=("%Y-%m-%dT%H:%M",),
        label="Price effective from",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_published") and not cleaned.get("is_active"):
            self.add_error("is_published", "An inactive Product cannot be published.")
        if cleaned.get("price_amount") is not None and cleaned.get("price_effective_start") is None:
            self.add_error("price_effective_start", "An effective time is required when entering a price.")
        if cleaned.get("price_amount") is None:
            cleaned["price_effective_start"] = None
        return cleaned


class StaffProductEditForm(forms.ModelForm):
    def __init__(self, data=None, *args, **kwargs):
        # Older callers omit the stock unit; omission must preserve it.
        if data is not None and "base_inventory_unit" not in data:
            data = data.copy()
            data["base_inventory_unit"] = kwargs["instance"].base_inventory_unit
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = Product
        fields = ("name", "description", "category", "base_inventory_unit", "is_active", "is_published")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        labels = {"is_published": "Show in public catalog", "is_active": "Active product",
                  "base_inventory_unit": "Stock unit"}
        help_texts = {"category": "Existing SKU and web address are preserved.",
                      "base_inventory_unit": "Cannot change after Inventory use."}


class StaffSaleUnitEditForm(forms.ModelForm):
    class Meta:
        model = ProductSaleUnit
        fields = ("name", "base_quantity", "is_active")
        labels = {"name": "Sale unit", "base_quantity": "Seedlings per sale unit", "is_active": "Active sale unit"}


class StaffPriceForm(forms.Form):
    sale_unit_id = forms.ModelChoiceField(queryset=ProductSaleUnit.objects.none(), label="Sale Unit")

    def __init__(self, *args, product, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sale_unit_id"].queryset = product.sale_units.all()
        self.fields["sale_unit_id"].label_from_instance = lambda unit: f"{unit.name} / {unit.base_quantity} {product.base_inventory_unit}"

    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Price per Sale Unit (KES)")
    effective_start = forms.DateTimeField(initial=timezone.now, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))
    effective_end = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))
    is_active = forms.BooleanField(required=False, initial=True, label="Active price")
