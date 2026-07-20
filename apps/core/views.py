from django.shortcuts import render

from apps.products.mock_data import CATEGORIES, PRODUCT_BY_SLUG


HOMEPAGE_FEATURED_SLUGS = (
    "anna-f1-tomato",
    "california-wonder-capsicum",
    "hass-avocado",
    "grevillea-robusta",
)


def home(request):
    """Render curated catalog records; the homepage never defines products."""
    featured_products = [PRODUCT_BY_SLUG[slug] for slug in HOMEPAGE_FEATURED_SLUGS]
    return render(
        request,
        "core/home.html",
        {"categories": CATEGORIES, "featured_products": featured_products},
    )


def about(request):
    return render(request, "core/about.html")


def faq(request):
    return render(request, "core/faq.html")
