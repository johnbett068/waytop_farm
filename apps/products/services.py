from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import Product, ProductPrice, ProductSaleUnit


def _require_permission(actor, permission):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Product catalog operation requires {permission}.")


def require_catalog_view(actor):
    _require_permission(actor, "products.view_product")


def require_catalog_create(actor):
    for permission in (
        "products.add_product",
        "products.add_productsaleunit",
        "products.add_productprice",
    ):
        _require_permission(actor, permission)


@transaction.atomic
def create_seedling_product(
    *, name, sku, slug, description, base_inventory_unit, is_active, is_published,
    sale_unit_name, sale_unit_base_quantity, price_amount, price_effective_start, actor
):
    """Create one canonical Product with its first sale unit and optional current KES price."""
    require_catalog_create(actor)
    name = (name or "").strip()
    sku = (sku or "").strip().upper()
    slug = (slug or "").strip().lower() or slugify(name)
    base_inventory_unit = (base_inventory_unit or "").strip().lower()
    sale_unit_name = (sale_unit_name or "").strip()
    if not name or not sku or not slug or not base_inventory_unit or not sale_unit_name:
        raise ValidationError("Product identity, base unit, and sale unit are required.")

    product = Product(
        name=name,
        sku=sku,
        slug=slug,
        description=(description or "").strip(),
        base_inventory_unit=base_inventory_unit,
        is_active=bool(is_active),
        is_published=bool(is_published),
    )
    product.full_clean()
    product.save()

    sale_unit = ProductSaleUnit(
        product=product,
        name=sale_unit_name,
        base_quantity=sale_unit_base_quantity,
        is_active=True,
    )
    sale_unit.full_clean()
    sale_unit.save()

    price = None
    if price_amount is not None:
        if price_effective_start is None:
            raise ValidationError({"price_effective_start": "Price effective time is required."})
        price = ProductPrice(
            sale_unit=sale_unit,
            amount=price_amount,
            currency=ProductPrice.Currency.KES,
            effective_start=price_effective_start,
            is_active=True,
        )
        price.save()
    return product, sale_unit, price

