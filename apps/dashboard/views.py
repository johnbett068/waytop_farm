from django.shortcuts import render

def dashboard(request):
    return render(request, "dashboard/dashboard.html", {"state_mode": request.GET.get("state", "success")})


def orders(request):
    return render(request, "dashboard/orders.html", {"state_mode": request.GET.get("state", "success")})


def order_detail(request, order_number):
    return render(request, "dashboard/order_detail.html", {"state_mode": request.GET.get("state", "success"), "order_number": order_number})


def production(request):
    return render(request, "dashboard/production/dashboard.html", {"state_mode": request.GET.get("state", "success")})


def source_lots(request):
    return render(request, "dashboard/production/source_lots.html", {"state_mode": request.GET.get("state", "success")})


def production_batches(request):
    return render(request, "dashboard/production/batches.html", {"state_mode": request.GET.get("state", "success")})


def production_batch_detail(request, batch_number):
    return render(request, "dashboard/production/batch_detail.html", {"state_mode": request.GET.get("state", "success"), "batch_number": batch_number})


def production_tasks(request):
    return render(request, "dashboard/production/tasks.html", {"state_mode": request.GET.get("state", "success")})


def production_exceptions(request):
    return render(request, "dashboard/production/exceptions.html", {"state_mode": request.GET.get("state", "success")})


def inventory(request):
    return render(request, "dashboard/inventory/dashboard.html", {"state_mode": request.GET.get("state", "success")})


def inventory_items(request):
    return render(request, "dashboard/inventory/items.html", {"state_mode": request.GET.get("state", "success")})


def inventory_item_detail(request, item_code):
    return render(request, "dashboard/inventory/item_detail.html", {"state_mode": request.GET.get("state", "success"), "item_code": item_code})


def inventory_lots(request):
    return render(request, "dashboard/inventory/lots.html", {"state_mode": request.GET.get("state", "success")})


def inventory_movements(request):
    return render(request, "dashboard/inventory/movements.html", {"state_mode": request.GET.get("state", "success")})


def inventory_receiving(request):
    return render(request, "dashboard/inventory/receiving.html", {"state_mode": request.GET.get("state", "success")})


def inventory_transfers(request):
    return render(request, "dashboard/inventory/transfers.html", {"state_mode": request.GET.get("state", "success")})


def inventory_counts(request):
    return render(request, "dashboard/inventory/counts.html", {"state_mode": request.GET.get("state", "success")})


def inventory_adjustments(request):
    return render(request, "dashboard/inventory/adjustments.html", {"state_mode": request.GET.get("state", "success")})


def procurement(request):
    return render(request, "dashboard/procurement/dashboard.html", {"state_mode": request.GET.get("state", "success")})


def suppliers(request):
    return render(request, "dashboard/procurement/suppliers.html", {"state_mode": request.GET.get("state", "success")})


def supplier_detail(request, supplier_code):
    return render(request, "dashboard/procurement/supplier_detail.html", {"state_mode": request.GET.get("state", "success"), "supplier_code": supplier_code})


def purchase_requests(request):
    return render(request, "dashboard/procurement/requests.html", {"state_mode": request.GET.get("state", "success")})


def purchase_request_detail(request, request_number):
    return render(request, "dashboard/procurement/request_detail.html", {"state_mode": request.GET.get("state", "success"), "request_number": request_number})


def purchase_orders(request):
    return render(request, "dashboard/procurement/orders.html", {"state_mode": request.GET.get("state", "success")})


def purchase_order_detail(request, order_number):
    return render(request, "dashboard/procurement/order_detail.html", {"state_mode": request.GET.get("state", "success"), "order_number": order_number})


def procurement_receiving(request):
    return render(request, "dashboard/procurement/receiving.html", {"state_mode": request.GET.get("state", "success")})


def supplier_performance(request):
    return render(request, "dashboard/procurement/performance.html", {"state_mode": request.GET.get("state", "success")})


def pos(request):
    return render(request, "dashboard/pos/dashboard.html", {"state_mode": request.GET.get("state", "success")})


def pos_sale(request):
    return render(request, "dashboard/pos/sale.html", {"state_mode": request.GET.get("state", "success")})


def pos_parked(request):
    return render(request, "dashboard/pos/parked.html", {"state_mode": request.GET.get("state", "success")})


def pos_transactions(request):
    return render(request, "dashboard/pos/transactions.html", {"state_mode": request.GET.get("state", "success")})


def pos_receipt(request, transaction_reference):
    return render(request, "dashboard/pos/receipt.html", {"state_mode": request.GET.get("state", "success"), "transaction_reference": transaction_reference})


def delivery(request):
    return render(request, "dashboard/delivery/dashboard.html", {"state_mode": request.GET.get("state", "success")})


def delivery_jobs(request):
    return render(request, "dashboard/delivery/jobs.html", {"state_mode": request.GET.get("state", "success")})


def delivery_job_detail(request, delivery_number):
    return render(request, "dashboard/delivery/job_detail.html", {"state_mode": request.GET.get("state", "success"), "delivery_number": delivery_number})
