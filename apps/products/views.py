from django.http import Http404
from django.shortcuts import render

from .mock_data import CATEGORIES, CATEGORY_BY_SLUG, PRODUCTS, PRODUCT_BY_SLUG, product_page_context


def shop(request):
    return render(request, "products/shop.html", {"products": PRODUCTS, "categories": CATEGORIES, "catalog_mode": "shop"})


def product_detail(request, slug):
    product = PRODUCT_BY_SLUG.get(slug)
    if not product:
        raise Http404("Product not found")
    return render(request, "products/product_detail.html", product_page_context(product))


def categories(request):
    return render(request, "products/categories.html", {"categories": CATEGORIES})


def category(request, slug):
    category_data = CATEGORY_BY_SLUG.get(slug)
    if not category_data:
        raise Http404("Category not found")
    products = [product for product in PRODUCTS if product["category_slug"] == slug]
    return render(request, "products/category.html", {"products": products, "categories": CATEGORIES, "category": category_data, "catalog_mode": "category"})


def search(request):
    return render(request, "products/search.html", {"products": PRODUCTS, "categories": CATEGORIES, "catalog_mode": "search"})
