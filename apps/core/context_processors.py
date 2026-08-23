from django.conf import settings

def business_contact(request):
    """Expose the canonical business phone number to every template."""
    phone = settings.WAYTOP_CONTACT_PHONE
    digits = phone.removeprefix("+")
    display = f"+{digits[:3]} {digits[3:6]} {digits[6:9]} {digits[9:]}"
    return {"business_phone": {"uri": phone, "display": display}}


def commerce_catalog(request):
    """Expose no products until the authoritative Catalog read model exists."""
    return {"commerce_catalog": []}
