from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.production.forms import (
    ActivityForm,
    BatchCreateForm,
    BatchTransitionForm,
    BatchUpdateForm,
    LabourForm,
    PurchaseForm,
)
from apps.production.models import (
    NurseryActivity,
    ProductionBatch,
    ProductionLabour,
    ProductionPurchase,
)
from apps.production.services import (
    LEGAL_TRANSITIONS,
    create_batch,
    record_activity,
    record_labour,
    record_purchase,
    require_view_permission,
    transition_batch,
    update_batch,
)
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.inventory.supply_services import require_supply_view
from .queries import build_operations_dashboard


@login_required(login_url="accounts:login")
def _empty(request, *, title, eyebrow, message):
    if not request.user.is_active or not request.user.is_staff:
        raise PermissionDenied
    return render(
        request,
        "dashboard/empty.html",
        {"page_title": title, "page_eyebrow": eyebrow, "empty_message": message},
    )


@login_required(login_url="accounts:login")
def dashboard(request):
    snapshot = build_operations_dashboard(actor=request.user)
    return render(
        request,
        "dashboard/dashboard.html",
        {"operations": snapshot},
    )


def orders(request):
    return _empty(request, title="Orders", eyebrow="Order operations", message="No orders yet.")


def order_detail(request, order_number):
    return _empty(request, title="Order not found", eyebrow="Order operations", message="No persisted order matches this reference.")


@login_required(login_url="accounts:login")
def production(request):
    require_view_permission(request.user)
    active = ProductionBatch.objects.filter(status=ProductionBatch.Status.IN_PRODUCTION)
    context = {
        "active_batches": active.select_related("product")[:8],
        "active_count": active.count(),
        "in_production_quantity": active.aggregate(total=Sum("current_quantity"))["total"] or 0,
        "ready_count": ProductionBatch.objects.filter(status=ProductionBatch.Status.READY).count(),
        "recent_activities": NurseryActivity.objects.select_related("batch", "recorded_by")[:8],
        "recent_purchases": ProductionPurchase.objects.select_related("batch", "recorded_by")[:6],
        "recent_labour": ProductionLabour.objects.select_related("batch", "recorded_by")[:6],
    }
    return render(request, "dashboard/production/dashboard.html", context)


def source_lots(request):
    return _empty(request, title="Production source lots", eyebrow="Production", message="No production source lots yet.")


@login_required(login_url="accounts:login")
def production_batches(request):
    require_view_permission(request.user)
    batches = ProductionBatch.objects.select_related("product", "created_by")
    status = request.GET.get("status", "").strip()
    if status in ProductionBatch.Status.values:
        batches = batches.filter(status=status)
    return render(
        request,
        "dashboard/production/batches.html",
        {"batches": batches, "selected_status": status, "statuses": ProductionBatch.Status.choices},
    )


@login_required(login_url="accounts:login")
def production_batch_detail(request, batch_number):
    require_view_permission(request.user)
    batch = get_object_or_404(
        ProductionBatch.objects.select_related("product", "created_by"),
        batch_number=batch_number,
    )
    next_status = LEGAL_TRANSITIONS.get(batch.status)
    return render(
        request,
        "dashboard/production/batch_detail.html",
        {
            "batch": batch,
            "events": batch.history.select_related("actor")[:30],
            "activities": batch.activities.select_related("recorded_by")[:10],
            "purchases": batch.purchases.select_related("recorded_by")[:10],
            "labour_records": batch.labour_records.select_related("recorded_by")[:10],
            "purchase_total": batch.purchases.aggregate(total=Sum("total_cost"))["total"] or 0,
            "labour_total": batch.labour_records.aggregate(total=Sum("total_cost"))["total"] or 0,
            "activity_total": batch.activities.aggregate(total=Sum("cost"))["total"] or 0,
            "next_status": next_status,
            "next_status_label": dict(ProductionBatch.Status.choices).get(next_status),
            "transition_form": BatchTransitionForm(initial={"to_status": next_status}) if next_status else None,
        },
    )


def _require_capability(actor, permission):
    if (
        not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Production operation requires {permission}.")


def _service_error(form, error):
    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            target = field if field in form.fields else None
            for message in errors:
                form.add_error(target, message)
    else:
        form.add_error(None, error)


@login_required(login_url="accounts:login")
def production_batch_create(request):
    _require_capability(request.user, "production.manage_batches")
    form = BatchCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            batch = create_batch(
                batch_number=values["batch_number"],
                product_id=values["product"].pk,
                start_date=values["start_date"],
                expected_ready_date=values["expected_ready_date"],
                quantity_started=values["quantity_started"],
                location_id=values["location"].pk if values["location"] else None,
                notes=values["notes"],
                actor=request.user,
                correlation_id=values["correlation_id"],
                idempotency_key=values["idempotency_key"],
            )
        except Exception as error:
            from django.core.exceptions import ValidationError
            if not isinstance(error, ValidationError):
                raise
            _service_error(form, error)
        else:
            messages.success(request, f"Production batch {batch.batch_number} created.")
            return redirect("dashboard:production_batch_detail", batch_number=batch.batch_number)
    return render(request, "dashboard/production/record_form.html", {
        "form": form, "title": "New Production batch", "eyebrow": "Production",
        "submit_label": "Create batch", "cancel_url": "dashboard:production",
        "show_catalog_link": True,
    })


@login_required(login_url="accounts:login")
def production_batch_update(request, batch_number):
    _require_capability(request.user, "production.manage_batches")
    batch = get_object_or_404(ProductionBatch, batch_number=batch_number)
    initial = {
        "current_quantity": batch.current_quantity,
        "location": batch.location_id,
        "expected_ready_date": batch.expected_ready_date,
        "notes": batch.notes,
    }
    form = BatchUpdateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            update_batch(
                batch_id=batch.pk,
                current_quantity=values["current_quantity"],
                location_id=values["location"].pk if values["location"] else None,
                expected_ready_date=values["expected_ready_date"],
                notes=values["notes"],
                reason=values["reason"],
                actor=request.user,
                correlation_id=values["correlation_id"],
                idempotency_key=values["idempotency_key"],
            )
        except Exception as error:
            from django.core.exceptions import ValidationError
            if not isinstance(error, ValidationError):
                raise
            _service_error(form, error)
        else:
            messages.success(request, f"Production batch {batch.batch_number} updated.")
            return redirect("dashboard:production_batch_detail", batch_number=batch.batch_number)
    return render(request, "dashboard/production/record_form.html", {
        "form": form, "title": f"Update {batch.batch_number}", "eyebrow": "Production batch",
        "submit_label": "Save update", "cancel_url": "dashboard:production_batch_detail",
        "cancel_arg": batch.batch_number,
    })


@login_required(login_url="accounts:login")
def production_batch_transition(request, batch_number):
    _require_capability(request.user, "production.manage_batches")
    if request.method != "POST":
        return redirect("dashboard:production_batch_detail", batch_number=batch_number)
    batch = get_object_or_404(ProductionBatch, batch_number=batch_number)
    form = BatchTransitionForm(request.POST)
    if form.is_valid():
        values = form.cleaned_data
        try:
            transition_batch(
                batch_id=batch.pk,
                to_status=values["to_status"],
                reason=values["reason"],
                actor=request.user,
                correlation_id=values["correlation_id"],
                idempotency_key=values["idempotency_key"],
            )
        except Exception as error:
            from django.core.exceptions import ValidationError
            if not isinstance(error, ValidationError):
                raise
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, f"Production batch moved to {values['to_status']}.")
    else:
        messages.error(request, "A transition reason and valid command identity are required.")
    return redirect("dashboard:production_batch_detail", batch_number=batch.batch_number)


def _record_form(request, *, permission, form_class, service, title, submit_label):
    _require_capability(request.user, permission)
    initial = {"purchase_date": timezone.localdate(), "work_date": timezone.localdate(), "activity_date": timezone.localdate()}
    requested_batch = request.GET.get("batch", "")
    if requested_batch:
        initial["batch"] = ProductionBatch.objects.filter(batch_number=requested_batch).first()
    form = form_class(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data.copy()
        batch = values.pop("batch", None)
        values["batch_id"] = batch.pk if batch else None
        values["actor"] = request.user
        try:
            record = service(**values)
        except Exception as error:
            from django.core.exceptions import ValidationError
            if not isinstance(error, ValidationError):
                raise
            _service_error(form, error)
        else:
            messages.success(request, f"{title} recorded.")
            if record.batch_id:
                return redirect("dashboard:production_batch_detail", batch_number=record.batch.batch_number)
            return redirect("dashboard:production")
    return render(request, "dashboard/production/record_form.html", {
        "form": form, "title": title, "eyebrow": "Production operations",
        "submit_label": submit_label, "cancel_url": "dashboard:production",
    })


@login_required(login_url="accounts:login")
def production_purchase_create(request):
    return _record_form(
        request, permission="production.record_purchases", form_class=PurchaseForm,
        service=record_purchase, title="Production purchase", submit_label="Record purchase",
    )


@login_required(login_url="accounts:login")
def production_labour_create(request):
    return _record_form(
        request, permission="production.record_labour", form_class=LabourForm,
        service=record_labour, title="Production labour", submit_label="Record labour",
    )


@login_required(login_url="accounts:login")
def production_activity_create(request):
    return _record_form(
        request, permission="production.record_activities", form_class=ActivityForm,
        service=record_activity, title="Nursery activity", submit_label="Record activity",
    )


def production_tasks(request):
    return _empty(request, title="Production tasks", eyebrow="Production", message="No production tasks yet.")


def production_exceptions(request):
    return _empty(request, title="Production exceptions", eyebrow="Production", message="No production exceptions yet.")


@login_required(login_url="accounts:login")
def inventory(request):
    require_supply_view(request.user)
    items = list(
        InventoryItem.objects.select_related("product", "supply")
        .annotate(total_on_hand=Sum("positions__on_hand_base_quantity"))
        .order_by("kind", "product__name", "supply__name")
    )
    product_items = [item for item in items if item.kind == InventoryItem.Kind.PRODUCT]
    supply_items = [item for item in items if item.kind == InventoryItem.Kind.SUPPLY]
    out_of_stock_count = sum(
        1 for item in items if not item.total_on_hand or item.total_on_hand <= 0
    )
    recent_movements = (
        InventoryMovement.objects.select_related("actor")
        .prefetch_related("lines__item__product", "lines__item__supply", "lines__lot")[:8]
    )
    return render(request, "dashboard/inventory/dashboard_live.html", {
        "product_items": product_items,
        "supply_items": supply_items,
        "product_count": len(product_items),
        "supply_count": len(supply_items),
        "out_of_stock_count": out_of_stock_count,
        "recent_movements": recent_movements,
    })


def inventory_items(request):
    return _empty(request, title="Inventory items", eyebrow="Inventory", message="No inventory items yet.")


def inventory_item_detail(request, item_code):
    return _empty(request, title="Inventory item not found", eyebrow="Inventory", message="No persisted inventory item matches this reference.")


def inventory_lots(request):
    return _empty(request, title="Inventory lots", eyebrow="Inventory", message="No inventory lots yet.")


def inventory_movements(request):
    return _empty(request, title="Inventory movements", eyebrow="Inventory", message="No inventory movements yet.")


def inventory_receiving(request):
    return _empty(request, title="Inventory receiving", eyebrow="Inventory", message="No inventory receipts yet.")


def inventory_transfers(request):
    return _empty(request, title="Inventory transfers", eyebrow="Inventory", message="No inventory transfers yet.")


def inventory_counts(request):
    return _empty(request, title="Inventory counts", eyebrow="Inventory", message="No inventory counts yet.")


def inventory_adjustments(request):
    return _empty(request, title="Inventory adjustments", eyebrow="Inventory", message="No inventory adjustments yet.")


def pos(request):
    return _empty(request, title="Point of Sale", eyebrow="POS order entry", message="No POS orders or transactions yet.")


def pos_sale(request):
    return _empty(request, title="New POS order", eyebrow="POS order entry", message="No authoritative products or stock are available for POS order entry.")
