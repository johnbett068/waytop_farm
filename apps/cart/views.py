from django.shortcuts import render

from apps.products.catalog import commerce_catalog_projection, public_catalog_products


def cart(request):
    products = public_catalog_products()
    return render(request, "cart/cart.html", {
        "state_mode": request.GET.get("state", "success"),
        "commerce_catalog": commerce_catalog_projection(products),
    })
