import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .acquisitions import acquire_external_stock
from .adjustments import approve_inventory_adjustment, request_inventory_adjustment
from .forms import AdjustmentApprovalForm, AdjustmentRequestForm, LocationForm, StockAcquisitionForm, SupplyForm
from .location_services import save_location
from .services import _require_permission
from .models import (
    InventoryAdjustmentRequest, InventoryLocation, InventoryMovement, InventorySupply, StockPosition,
)
from .supply_services import create_inventory_supply, require_supply_view, update_inventory_supply


def _audit_initial(): return {"correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4()}


def _errors(form, error):
    if hasattr(error, "message_dict"):
        for field, values in error.message_dict.items():
            for value in values: form.add_error(field if field in form.fields else None, value)
    else: form.add_error(None, error)


@login_required(login_url="accounts:login")
def location_list(request):
    require_supply_view(request.user)
    return render(request, "dashboard/inventory/locations_live.html", {
        "locations": InventoryLocation.objects.order_by("name", "pk"),
    })


@login_required(login_url="accounts:login")
def location_form(request, location_id=None):
    require_supply_view(request.user)
    _require_permission(request.user, "inventory.change_inventorylocation" if location_id else "inventory.add_inventorylocation")
    location = get_object_or_404(InventoryLocation, pk=location_id) if location_id else None
    form = LocationForm(request.POST or None, initial={
        "name": location.name if location else "", "idempotency_key": uuid.uuid4(),
    })
    if request.method == "POST" and form.is_valid():
        try:
            saved = save_location(location_id=location.pk if location else None,
                                  actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _errors(form, error)
        else:
            messages.success(request, f"Location {saved.name} saved.")
            return redirect("dashboard:inventory_location_list")
    return render(request, "dashboard/inventory/location_form_live.html", {
        "form": form, "title": "Edit Location" if location else "Add Location",
    })


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
    initial = _audit_initial()
    initial["acquisition_date"] = timezone.localdate()
    form = StockAcquisitionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            acquisition = acquire_external_stock(
                product_id=data["product"].pk, quantity=data["quantity"],
                unit_cost=data["unit_cost"], acquisition_date=data["acquisition_date"],
                supplier_id=data["supplier"].pk if data["supplier"] else None,
                location_id=data["location"].pk, supplier_batch_reference=data["supplier_batch_reference"],
                condition=data["condition"],
                reference=data["reference"], note=data["note"], actor=request.user,
                correlation_id=data["correlation_id"], idempotency_key=data["idempotency_key"],
            )
        except ValidationError as error: _errors(form, error)
        else:
            messages.success(request, f"Acquired {acquisition.movement_line.quantity} {acquisition.movement_line.item.base_unit} of {acquisition.movement_line.item.product.name}.")
            return redirect("dashboard:inventory_stock")
    return render(request, "dashboard/inventory/receipt_form_live.html", {
        "form": form, "title": "Acquire Stock", "cancel_url": "dashboard:inventory_stock",
    })


@login_required(login_url="accounts:login")
def stock(request):
    require_supply_view(request.user)
    positions = StockPosition.objects.select_related("item__product", "item__supply", "lot", "location")
    return render(request, "dashboard/inventory/stock_live.html", {"positions": positions})


@login_required(login_url="accounts:login")
def history(request):
    require_supply_view(request.user)
    movements = InventoryMovement.objects.prefetch_related(
        "lines__item__product", "lines__item__supply", "lines__lot",
        "lines__source_location", "lines__destination_location",
    ).select_related("actor", "external_acquisition__supplier")
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
