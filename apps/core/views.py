from django.shortcuts import render

from apps.products.catalog import commerce_catalog_projection, public_catalog_products

def home(request):
    products = public_catalog_products()
    return render(
        request,
        "core/home.html",
        {
            "categories": [],
            "featured_products": products[:4],
            "commerce_catalog": commerce_catalog_projection(products),
        },
    )


def about(request):
    return render(request, "core/about.html")


def faq(request):
    return render(request, "core/faq.html")
