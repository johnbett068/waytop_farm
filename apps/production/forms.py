import uuid

from django import forms

from apps.products.models import Product

from .models import NurseryActivity, ProductionBatch, ProductionLabour, ProductionPurchase


class AuditCommandForm(forms.Form):
    correlation_id = forms.UUIDField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("correlation_id", uuid.uuid4())
            self.initial.setdefault("idempotency_key", uuid.uuid4())


class BatchCreateForm(AuditCommandForm):
    batch_number = forms.CharField(max_length=64)
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        label="Seedling product",
        help_text="Only active Products from the WayTop Farm catalog appear here.",
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    expected_ready_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    quantity_started = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_active=True).order_by("name", "sku")


class BatchUpdateForm(AuditCommandForm):
    current_quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0)
    expected_ready_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))


class BatchTransitionForm(AuditCommandForm):
    to_status = forms.ChoiceField(choices=ProductionBatch.Status.choices)
    reason = forms.CharField(max_length=500)


class BatchOptionalForm(AuditCommandForm):
    batch = forms.ModelChoiceField(
        queryset=ProductionBatch.objects.none(), required=False, empty_label="No specific batch"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = ProductionBatch.objects.exclude(
            status=ProductionBatch.Status.CLOSED
        ).select_related("product")


class PurchaseForm(BatchOptionalForm):
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    supplier = forms.CharField(max_length=200)
    item_description = forms.CharField(max_length=250)
    category = forms.ChoiceField(choices=ProductionPurchase.Category.choices)
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    unit = forms.CharField(max_length=50)
    unit_cost = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    reference = forms.CharField(max_length=120, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class LabourForm(BatchOptionalForm):
    work_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    worker = forms.CharField(max_length=200, label="Worker, person or team")
    activity = forms.CharField(max_length=250)
    effort_quantity = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    effort_unit = forms.ChoiceField(choices=ProductionLabour.EffortUnit.choices)
    rate = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ActivityForm(BatchOptionalForm):
    activity_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    activity_type = forms.ChoiceField(choices=NurseryActivity.Type.choices)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    coverage_quantity = forms.DecimalField(
        max_digits=12, decimal_places=3, min_value=0.001, required=False
    )
    coverage_unit = forms.CharField(max_length=50, required=False)
    person_or_team = forms.CharField(max_length=200, required=False)
    cost = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("coverage_quantity") is not None) != bool(cleaned.get("coverage_unit")):
            raise forms.ValidationError(
                "Coverage quantity and coverage unit must be supplied together."
            )
        return cleaned
