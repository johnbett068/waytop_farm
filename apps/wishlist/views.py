from django.shortcuts import render

from apps.products.catalog import commerce_catalog_projection, public_catalog_products


def wishlist(request):
    products = public_catalog_products()
    return render(request, "wishlist/wishlist.html", {
        "state_mode": request.GET.get("state", "success"),
        "commerce_catalog": commerce_catalog_projection(products),
    })
