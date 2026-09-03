from django import forms
from django.utils import timezone


class StaffProductCreateForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        label="Product name",
        help_text="Use the seedling name customers and nursery staff recognize.",
    )
    sku = forms.CharField(
        max_length=64,
        label="SKU",
        help_text="A unique internal catalog code, for example WTP-VEG-001.",
    )
    slug = forms.SlugField(
        max_length=160,
        required=False,
        label="Web address slug",
        help_text="Optional. Leave blank to generate it from the product name.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="A truthful description of the seedling sold by WayTop Farm.",
    )
    base_inventory_unit = forms.CharField(
        max_length=50,
        label="Base unit",
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

