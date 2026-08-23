from django.shortcuts import render

def checkout(request):
    return render(request, "orders/unavailable.html", {"page_title": "Checkout", "empty_title": "Checkout is not available yet", "empty_message": "No authoritative products or stock are available for ordering."})

def success(request):
    return render(request, "orders/unavailable.html", {"page_title": "Order confirmation", "empty_title": "No order confirmation is available", "empty_message": "No persisted order has been created."})

def tracking(request):
    return render(request, "orders/unavailable.html", {"page_title": "Order tracking", "empty_title": "No orders are available to track", "empty_message": "Order tracking will become available when persisted Orders exist."})

def history(request):
    return render(request, "orders/unavailable.html", {"page_title": "Order history", "empty_title": "No order history yet", "empty_message": "Persisted customer orders will appear here."})
