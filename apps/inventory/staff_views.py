import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.procurement.forms import GoodsReceiptForm
from apps.procurement.services import ReceiptLineInput, post_goods_receipt

from .adjustments import approve_inventory_adjustment, request_inventory_adjustment
from .forms import AdjustmentApprovalForm, AdjustmentRequestForm, SupplyForm
from .models import (
    InventoryAdjustmentRequest, InventoryMovement, InventorySupply, StockPosition,
)
from .supply_services import create_inventory_supply, require_supply_view, update_inventory_supply


def _audit_initial(): return {"correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4()}


def _errors(form, error):
    if hasattr(error, "message_dict"):
        for field, values in error.message_dict.items():
            for value in values: form.add_error(field if field in form.fields else None, value)
    else: form.add_error(None, error)


@login_required(login_url="accounts:login")
def supply_list(request):
    require_supply_view(request.user)
    return render(request, "dashboard/inventory/supplies_live.html", {"supplies": InventorySupply.objects.all()})


@login_required(login_url="accounts:login")
def supply_create(request):
    require_supply_view(request.user)
    form = SupplyForm(request.POST or None, initial=_audit_initial())
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            supply = create_inventory_supply(
                code=data["code"], name=data["name"], category=data["category"],
                base_unit=data["base_unit"],
                allows_fractional_quantity=data["allows_fractional_quantity"],
                actor=request.user, reason=data["reason"],
                correlation_id=data["correlation_id"], idempotency_key=data["idempotency_key"],
            )
        except ValidationError as error: _errors(form, error)
        else:
            messages.success(request, f"Supply {supply.code} created.")
            return redirect("dashboard:inventory_supply_detail", supply.code)
    return render(request, "dashboard/inventory/form_live.html", {
        "form": form, "title": "New Inventory Supply", "cancel_url": "dashboard:inventory_supply_list",
    })


@login_required(login_url="accounts:login")
def supply_edit(request, code):
    require_supply_view(request.user)
    supply = get_object_or_404(InventorySupply, code=code)
    initial = _audit_initial()
    initial.update({
        "code": supply.code, "name": supply.name, "category": supply.category,
        "base_unit": supply.base_unit,
        "allows_fractional_quantity": supply.allows_fractional_quantity,
        "is_active": supply.is_active,
    })
    form = SupplyForm(request.POST or None, initial=initial)
    form.fields["code"].disabled = True
    form.fields["base_unit"].disabled = True
    form.fields["allows_fractional_quantity"].disabled = True
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            supply = update_inventory_supply(
                supply_id=supply.pk, name=data["name"], category=data["category"],
                is_active=data["is_active"], actor=request.user, reason=data["reason"],
                correlation_id=data["correlation_id"], idempotency_key=data["idempotency_key"],
            )
        except ValidationError as error:
            _errors(form, error)
        else:
            messages.success(request, f"Supply {supply.code} updated.")
            return redirect("dashboard:inventory_supply_detail", supply.code)
    return render(request, "dashboard/inventory/form_live.html", {
        "form": form, "title": f"Edit {supply.code}",
        "cancel_url": "dashboard:inventory_supply_detail", "cancel_arg": supply.code,
    })


@login_required(login_url="accounts:login")
def supply_detail(request, code):
    require_supply_view(request.user)
    supply = get_object_or_404(InventorySupply.objects.prefetch_related("history"), code=code)
    positions = StockPosition.objects.filter(item=supply.inventory_item).select_related("lot", "location")
    return render(request, "dashboard/inventory/supply_detail_live.html", {"supply": supply, "positions": positions})


@login_required(login_url="accounts:login")
def receipt_create(request):
    require_supply_view(request.user)
    form = GoodsReceiptForm(request.POST or None, initial=_audit_initial())
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        line = data["purchase_order_line"]
        try:
            receipt = post_goods_receipt(
                number=data["number"], purchase_order_id=line.purchase_order_id,
                delivery_note_reference=data["delivery_note_reference"], receipt_date=data["receipt_date"],
                lines=(ReceiptLineInput(
                    purchase_order_line_id=line.pk,
                    accepted_base_quantity=data["accepted_base_quantity"],
                    rejected_base_quantity=data["rejected_base_quantity"],
                    rejection_reason=data["rejection_reason"], lot_code=data["lot_code"],
                    destination_location_id=data["destination_location"].pk,
                ),), actor=request.user, reason=data["reason"],
                correlation_id=data["correlation_id"], idempotency_key=data["idempotency_key"],
            )
        except ValidationError as error: _errors(form, error)
        else:
            messages.success(request, f"Goods Receipt {receipt.number} posted.")
            return redirect("dashboard:inventory_history")
    return render(request, "dashboard/inventory/receipt_form_live.html", {
        "form": form, "title": "Receive Supplier Stock", "cancel_url": "dashboard:inventory_stock",
    })


@login_required(login_url="accounts:login")
def stock(request):
    require_supply_view(request.user)
    positions = StockPosition.objects.filter(item__kind="SUPPLY").select_related("item__supply", "lot", "location")
    return render(request, "dashboard/inventory/stock_live.html", {"positions": positions})


@login_required(login_url="accounts:login")
def history(request):
    require_supply_view(request.user)
    movements = InventoryMovement.objects.filter(lines__item__kind="SUPPLY").distinct().prefetch_related(
        "lines__item__supply", "lines__lot", "lines__source_location", "lines__destination_location"
    ).select_related("actor")
    return render(request, "dashboard/inventory/history_live.html", {"movements": movements})


@login_required(login_url="accounts:login")
def adjustments(request):
    require_supply_view(request.user)
    return render(request, "dashboard/inventory/adjustments_live.html", {
        "adjustments": InventoryAdjustmentRequest.objects.select_related("item__supply", "requester", "approver"),
        "request_form": AdjustmentRequestForm(initial=_audit_initial()),
        "approval_form": AdjustmentApprovalForm(initial=_audit_initial()),
    })


@login_required(login_url="accounts:login")
def adjustment_request(request):
    require_supply_view(request.user)
    if request.method == "POST":
        form = AdjustmentRequestForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                request_inventory_adjustment(
                    item_id=data["item"].pk, lot_id=data["lot"].pk,
                    location_id=data["location"].pk, direction=data["direction"],
                    base_quantity=data["base_quantity"], actor=request.user,
                    reason=data["reason"], correlation_id=data["correlation_id"],
                    idempotency_key=data["idempotency_key"],
                )
            except ValidationError as error: messages.error(request, "; ".join(error.messages))
            else: messages.success(request, "Adjustment requested.")
    return redirect("dashboard:inventory_adjustments")


@login_required(login_url="accounts:login")
def adjustment_approve(request):
    require_supply_view(request.user)
    if request.method == "POST":
        form = AdjustmentApprovalForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                approve_inventory_adjustment(
                    adjustment_id=data["adjustment"].pk, actor=request.user,
                    reason=data["reason"], correlation_id=data["correlation_id"],
                    idempotency_key=data["idempotency_key"],
                )
            except (ValidationError, PermissionDenied) as error:
                messages.error(request, str(error))
            else: messages.success(request, "Adjustment approved and posted.")
    return redirect("dashboard:inventory_adjustments")
