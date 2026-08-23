from django.shortcuts import render

from .catalog import commerce_catalog_projection, public_catalog_products

def shop(request):
    products = public_catalog_products()
    return render(request, "products/shop.html", {
        "products": products,
        "categories": [],
        "catalog_mode": "shop",
        "commerce_catalog": commerce_catalog_projection(products),
    })


def product_detail(request, slug):
    products = public_catalog_products()
    product = next((item for item in products if item.slug == slug), None)
    if product is None:
        from django.http import Http404
        raise Http404("Product not found")
    return render(request, "products/product_detail.html", {
        "product": product,
        "commerce_catalog": commerce_catalog_projection(products),
    })


def categories(request):
    return render(request, "products/categories.html", {"categories": []})


def category(request, slug):
    from django.http import Http404
    raise Http404("Category not found")


def search(request):
    query = request.GET.get("q", "").strip()
    all_products = public_catalog_products()
    products = public_catalog_products(search=query) if query else all_products
    return render(request, "products/search.html", {
        "products": products,
        "categories": [],
        "catalog_mode": "search",
        "search_query": query,
        "commerce_catalog": commerce_catalog_projection(all_products),
    })
