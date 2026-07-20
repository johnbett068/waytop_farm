from django.conf import settings

from apps.products.mock_data import PRODUCTS


def business_contact(request):
    """Expose the canonical business phone number to every template."""
    phone = settings.WAYTOP_CONTACT_PHONE
    digits = phone.removeprefix("+")
    display = f"+{digits[:3]} {digits[3:6]} {digits[6:9]} {digits[9:]}"
    return {"business_phone": {"uri": phone, "display": display}}


def commerce_catalog(request):
    """Expose the frontend-only commerce read contract from the master catalog."""
    products = []
    for product in PRODUCTS:
        products.append({
            "slug": product["slug"], "sku": product["sku"], "name": product["name"],
            "variety": product["variety"], "category": product["category"],
            "price": product["price"], "price_display": product["price_display"],
            "unit": product["unit"], "stock": product["stock"],
            "stock_label": product["stock_label"],
            "image_url": f"{settings.STATIC_URL}{product['image_filename']}",
            "product_url": f"/products/{product['slug']}/",
        })
    return {"commerce_catalog": products}
