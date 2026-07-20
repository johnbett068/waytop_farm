from django.shortcuts import render


def wishlist(request):
    return render(request, "wishlist/wishlist.html", {"state_mode": request.GET.get("state", "success")})
