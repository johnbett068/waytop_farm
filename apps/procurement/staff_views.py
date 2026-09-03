import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PurchaseOrderForm, PurchaseTransitionForm, SupplierForm
from .models import Supplier, SupplierPurchaseOrder
from .services import (
    PurchaseLineInput, create_purchase_order, require_procurement_view, save_supplier,
    transition_purchase_order,
)


def _audit_initial(): return {"correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4()}


def _errors(form, error):
    if hasattr(error, "message_dict"):
        for field, values in error.message_dict.items():
            for value in values: form.add_error(field if field in form.fields else None, value)
    else: form.add_error(None, error)


@login_required(login_url="accounts:login")
def supplier_list(request):
    require_procurement_view(request.user)
    return render(request, "dashboard/procurement/suppliers_live.html", {"suppliers": Supplier.objects.all()})


@login_required(login_url="accounts:login")
def supplier_form(request, supplier_id=None):
    require_procurement_view(request.user)
    supplier = get_object_or_404(Supplier, pk=supplier_id) if supplier_id else None
    initial = _audit_initial()
    if supplier:
        initial.update({field: getattr(supplier, field) for field in (
            "code", "name", "contact_person", "phone", "email", "address", "notes", "is_active"
        )})
    form = SupplierForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            saved = save_supplier(
                supplier_id=supplier.pk if supplier else None, actor=request.user, **form.cleaned_data
            )
        except ValidationError as error: _errors(form, error)
        else:
            messages.success(request, f"Supplier {saved.code} saved.")
            return redirect("dashboard:procurement_supplier_list")
    return render(request, "dashboard/procurement/form_live.html", {
        "form": form, "title": "Edit Supplier" if supplier else "New Supplier",
        "cancel_url": "dashboard:procurement_supplier_list",
    })


@login_required(login_url="accounts:login")
def purchase_list(request):
    require_procurement_view(request.user)
    orders = SupplierPurchaseOrder.objects.select_related("supplier").prefetch_related("lines")
    return render(request, "dashboard/procurement/purchases_live.html", {"orders": orders})


@login_required(login_url="accounts:login")
def purchase_create(request):
    require_procurement_view(request.user)
    form = PurchaseOrderForm(request.POST or None, initial=_audit_initial())
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            po = create_purchase_order(
                number=data["number"], supplier_id=data["supplier"].pk,
                order_date=data["order_date"], expected_date=data["expected_date"],
                reference=data["reference"], notes=data["notes"],
                lines=(PurchaseLineInput(
                    supply_id=data["supply"].pk, ordered_quantity=data["ordered_quantity"],
                    purchase_unit=data["purchase_unit"],
                    base_quantity_per_purchase_unit=data["base_quantity_per_purchase_unit"],
                    unit_cost=data["unit_cost"],
                ),), actor=request.user, reason=data["reason"],
                correlation_id=data["correlation_id"], idempotency_key=data["idempotency_key"],
            )
        except ValidationError as error: _errors(form, error)
        else:
            messages.success(request, f"Purchase Order {po.number} created.")
            return redirect("dashboard:procurement_purchase_detail", po.number)
    return render(request, "dashboard/procurement/purchase_form_live.html", {
        "form": form, "title": "New Purchase Order", "cancel_url": "dashboard:procurement_purchase_list",
    })


@login_required(login_url="accounts:login")
def purchase_detail(request, number):
    require_procurement_view(request.user)
    po = get_object_or_404(
        SupplierPurchaseOrder.objects.select_related("supplier").prefetch_related("lines", "goods_receipts", "history"),
        number=number,
    )
    return render(request, "dashboard/procurement/purchase_detail_live.html", {
        "purchase": po, "transition_form": PurchaseTransitionForm(initial=_audit_initial()),
    })


@login_required(login_url="accounts:login")
def purchase_transition(request, number, action):
    require_procurement_view(request.user)
    if request.method != "POST": return redirect("dashboard:procurement_purchase_detail", number)
    form = PurchaseTransitionForm(request.POST)
    if form.is_valid():
        po = get_object_or_404(SupplierPurchaseOrder, number=number)
        target = SupplierPurchaseOrder.Status.ORDERED if action == "place" else SupplierPurchaseOrder.Status.CANCELLED
        try:
            transition_purchase_order(
                purchase_order_id=po.pk, to_status=target, actor=request.user, **form.cleaned_data
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else: messages.success(request, f"Purchase Order {number} updated.")
    return redirect("dashboard:procurement_purchase_detail", number)
