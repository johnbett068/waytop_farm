from django import forms
from django.db.models import Q

from apps.procurement.models import Supplier
from apps.products.models import Product

from .models import (
    InventoryAdjustmentRequest, InventoryItem, InventoryLocation, InventorySupply, StockLot,
)


class AuditForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    correlation_id = forms.UUIDField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


class SupplierChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, supplier):
        return supplier.name


class LocationForm(forms.Form):
    name = forms.CharField(max_length=160, label="Branch / Location name")
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


class LocationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, location):
        return location.name


class StockAcquisitionForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        help_text="The seedling Product entering the authoritative Inventory ledger.",
    )
    quantity = forms.DecimalField(
        max_digits=32, decimal_places=3, min_value=0.001,
        help_text="Quantity in the Product's Inventory base unit.",
        widget=forms.NumberInput(attrs={"step": "0.001"}),
    )
    unit_cost = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, label="Unit cost (KES)",
        help_text="Exact acquisition cost for one Inventory base unit.",
        widget=forms.NumberInput(attrs={"step": "0.01"}),
    )
    acquisition_date = forms.DateField(
        label="Acquisition date", widget=forms.DateInput(attrs={"type": "date"})
    )
    supplier = SupplierChoiceField(
        queryset=Supplier.objects.none(), required=False,
        help_text="Optional existing supplier or source attribution.",
    )
    location = LocationChoiceField(
        queryset=InventoryLocation.objects.none(),
        help_text="The WayTop Farm branch/site where the acquired seedlings are physically held.",
    )
    supplier_batch_reference = forms.CharField(
        max_length=100, required=False, label="Supplier Batch / Lot",
        help_text="Optional. Enter the batch or lot number provided by the supplier, if available.",
    )
    condition = forms.ChoiceField(
        choices=(("", "Select stock condition"),) + tuple(StockLot.Condition.choices),
        help_text="Uses the existing Inventory lot condition rules to determine availability.",
    )
    reference = forms.CharField(
        max_length=160, required=False,
        help_text="Optional invoice, receipt, or source reference.",
    )
    note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional acquisition context recorded on the Inventory receipt.",
    )
    correlation_id = forms.UUIDField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True,
        ).filter(
            Q(inventory_item__isnull=True)
            | Q(inventory_item__is_active=True, inventory_item__kind=InventoryItem.Kind.PRODUCT)
        ).order_by("name", "sku")
        self.fields["supplier"].queryset = Supplier.objects.order_by("name", "pk")
        self.fields["location"].queryset = InventoryLocation.objects.filter(is_active=True).order_by("name", "pk")


class SupplyForm(AuditForm):
    code = forms.CharField(
        max_length=64, label="Supply SKU / code",
        help_text="Stable internal code used to identify this supply.",
        widget=forms.TextInput(attrs={"placeholder": "SUP-SEED-TOM-001"}),
    )
    name = forms.CharField(
        max_length=200, label="Supply name",
        help_text="Use the name staff recognize when purchasing or handling this item.",
        widget=forms.TextInput(attrs={"placeholder": "Tomato Seeds — Rio Grande"}),
    )
    category = forms.ChoiceField(
        choices=InventorySupply.Category.choices,
        help_text="Choose the category that best describes the supply.",
    )
    base_unit = forms.CharField(
        max_length=50,
        help_text="The unit in which this supply is stored and counted in Inventory.",
        widget=forms.TextInput(attrs={"placeholder": "packet, kg, litre, tray, or piece"}),
    )
    allows_fractional_quantity = forms.BooleanField(
        required=False,
        help_text="Allow decimal quantities only when physically meaningful.",
    )
    is_active = forms.BooleanField(
        required=False, initial=True, label="Active supply",
        help_text="Inactive supplies remain in history but cannot be ordered or received.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].label = "Reason for this change"
        self.fields["reason"].help_text = "Explain why this supply definition is being created."


class AdjustmentRequestForm(AuditForm):
    item = forms.ModelChoiceField(queryset=InventoryItem.objects.none())
    lot = forms.ModelChoiceField(queryset=StockLot.objects.none())
    location = forms.ModelChoiceField(queryset=InventoryLocation.objects.none())
    direction = forms.ChoiceField(choices=InventoryAdjustmentRequest.Direction.choices)
    base_quantity = forms.DecimalField(max_digits=32, decimal_places=3, min_value=0.001)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = InventoryItem.objects.filter(kind="SUPPLY", is_active=True)
        self.fields["lot"].queryset = StockLot.objects.filter(item__kind="SUPPLY", is_active=True)
        self.fields["location"].queryset = InventoryLocation.objects.filter(is_active=True)


class AdjustmentApprovalForm(AuditForm):
    adjustment = forms.ModelChoiceField(queryset=InventoryAdjustmentRequest.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["adjustment"].queryset = InventoryAdjustmentRequest.objects.filter(state="PENDING")
