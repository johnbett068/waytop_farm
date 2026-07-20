from django.shortcuts import render

def checkout(request):
    return render(request, "orders/checkout.html", {"state_mode": request.GET.get("state", "auto")})

def success(request):
    return render(request, "orders/success.html", {"state_mode": request.GET.get("state", "success")})

def tracking(request):
    return render(request, "orders/tracking.html", {"state_mode": request.GET.get("state", "empty")})

def history(request):
    return render(request, "orders/tracking.html", {"state_mode": request.GET.get("state", "empty")})
