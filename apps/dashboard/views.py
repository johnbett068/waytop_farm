from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render


@login_required(login_url="accounts:login")
def _empty(request, *, title, eyebrow, message):
    if not request.user.is_staff:
        raise PermissionDenied
    return render(
        request,
        "dashboard/empty.html",
        {"page_title": title, "page_eyebrow": eyebrow, "empty_message": message},
    )


def dashboard(request):
    return _empty(request, title="Operations Dashboard", eyebrow="Operations", message="No operational data yet. Metrics and activity will appear when authoritative records exist.")


def orders(request):
    return _empty(request, title="Orders", eyebrow="Order operations", message="No orders yet.")


def order_detail(request, order_number):
    return _empty(request, title="Order not found", eyebrow="Order operations", message="No persisted order matches this reference.")


def production(request):
    return _empty(request, title="Production", eyebrow="Farm operations", message="No production batches yet.")


def source_lots(request):
    return _empty(request, title="Production source lots", eyebrow="Production", message="No production source lots yet.")


def production_batches(request):
    return _empty(request, title="Production batches", eyebrow="Production", message="No production batches yet.")


def production_batch_detail(request, batch_number):
    return _empty(request, title="Production batch not found", eyebrow="Production", message="No persisted production batch matches this reference.")


def production_tasks(request):
    return _empty(request, title="Production tasks", eyebrow="Production", message="No production tasks yet.")


def production_exceptions(request):
    return _empty(request, title="Production exceptions", eyebrow="Production", message="No production exceptions yet.")


def inventory(request):
    return _empty(request, title="Inventory", eyebrow="Farm operations", message="No inventory records yet.")


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
