from django import forms

from .models import (
    InventoryAdjustmentRequest, InventoryItem, InventoryLocation, InventorySupply, StockLot,
)


class AuditForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    correlation_id = forms.UUIDField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


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
