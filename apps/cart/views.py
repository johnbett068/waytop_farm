from django.shortcuts import render


def cart(request):
    return render(request, "cart/cart.html", {"state_mode": request.GET.get("state", "success")})
