from django import forms

from apps.inventory.models import InventoryLocation, InventorySupply

from .models import Supplier, SupplierPurchaseOrderLine


class AuditForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    correlation_id = forms.UUIDField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


class SupplierForm(forms.Form):
    name = forms.CharField(max_length=200, label="Supplier name")
    contact_person = forms.CharField(max_length=200, required=False)
    phone = forms.CharField(max_length=32, required=False)
    email = forms.EmailField(required=False)
    address = forms.CharField(label="Address / location", widget=forms.Textarea(attrs={"rows": 2}), required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    correlation_id = forms.UUIDField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


class PurchaseOrderForm(AuditForm):
    number = forms.CharField(
        max_length=64, label="WayTop purchase order number",
        help_text="WayTop's internal purchase order number, for example PO-2026-001.",
    )
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.none())
    order_date = forms.DateField(label="Order date", widget=forms.DateInput(attrs={"type": "date"}))
    expected_date = forms.DateField(
        label="Expected delivery date", widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    reference = forms.CharField(
        max_length=120, required=False, label="Supplier document / reference number",
        help_text="The supplier's quotation, invoice, receipt, or other reference number; this is not a quantity.",
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    supply = forms.ModelChoiceField(
        queryset=InventorySupply.objects.none(),
        help_text="A Supply is an operational item and is not sold through the customer Product catalog.",
    )
    ordered_quantity = forms.DecimalField(
        max_digits=32, decimal_places=3, min_value=0.001,
        widget=forms.NumberInput(attrs={"step": "0.001", "data-purchase-quantity": ""}),
    )
    purchase_unit = forms.CharField(
        max_length=50, help_text="How the supplier sells the item, such as packet, bag, tray, or carton."
    )
    base_quantity_per_purchase_unit = forms.DecimalField(
        max_digits=32, decimal_places=3, min_value=0.001,
        help_text="How many Inventory base units are contained in one supplier purchase unit.",
    )
    unit_cost = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
        label="Unit cost (KES)", help_text="The price of one purchase unit.",
        widget=forms.NumberInput(attrs={"step": "0.01", "data-purchase-unit-cost": ""}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)
        self.fields["supply"].queryset = InventorySupply.objects.filter(is_active=True)


class PurchaseTransitionForm(AuditForm):
    pass


class GoodsReceiptForm(AuditForm):
    number = forms.CharField(
        max_length=64, label="WayTop goods receipt number",
        help_text="Internal receipt identity, for example GRN-2026-001.",
    )
    purchase_order_line = forms.ModelChoiceField(
        queryset=SupplierPurchaseOrderLine.objects.none(),
        help_text="The ordered Supply and its purchase-unit conversion are fixed by this line.",
    )
    delivery_note_reference = forms.CharField(
        max_length=160, label="Supplier delivery note / reference"
    )
    receipt_date = forms.DateField(label="Date received", widget=forms.DateInput(attrs={"type": "date"}))
    accepted_base_quantity = forms.DecimalField(
        max_digits=32, decimal_places=3, min_value=0,
        label="Accepted quantity (Inventory base units)",
        help_text="Physical quantity accepted, expressed in the Supply's Inventory base unit.",
    )
    rejected_base_quantity = forms.DecimalField(
        max_digits=32, decimal_places=3, min_value=0,
        label="Rejected quantity (Inventory base units)",
    )
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False,
        help_text="Required when any delivered quantity is rejected.",
    )
    lot_code = forms.CharField(
        max_length=100, label="Supplier / internal lot reference",
        help_text="The supplier lot or WayTop internal lot identifier used for stock traceability.",
    )
    destination_location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.none(),
        help_text="The Inventory location where the accepted stock will be held.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order_line"].queryset = SupplierPurchaseOrderLine.objects.filter(
            purchase_order__status__in=("ORDERED", "PARTIALLY_RECEIVED"),
            supply__is_active=True,
        ).select_related("purchase_order", "supply")
        self.fields["destination_location"].queryset = InventoryLocation.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        accepted = cleaned.get("accepted_base_quantity") or 0
        rejected = cleaned.get("rejected_base_quantity") or 0
        if accepted <= 0:
            self.add_error("accepted_base_quantity", "A posted receipt requires accepted stock.")
        if rejected > 0 and not (cleaned.get("rejection_reason") or "").strip():
            self.add_error("rejection_reason", "Rejected quantity requires a reason.")
        return cleaned
