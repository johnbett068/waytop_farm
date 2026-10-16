import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import Product, ProductPrice, ProductSaleUnit, ProductSkuSequence


SKU_PATTERN = re.compile(r"^WTP-(VEG|FRT|TRE)-(\d+)$")


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


def _next_product_sku(category):
    if category not in Product.Category.values:
        raise ValidationError({"category": "Select a valid Product category."})

    # Lock in a stable order so Product identity allocation is one serialized
    # operation, including collision-free slug selection below.
    sequences = {
        sequence.category: sequence
        for sequence in ProductSkuSequence.objects.select_for_update().order_by("category")
    }
    if set(sequences) != set(Product.Category.values):
        raise ValidationError("Product SKU sequences are not configured correctly.")

    prefix = f"WTP-{category}-"
    highest_existing = 0
    for existing_sku in Product.objects.filter(sku__startswith=prefix).values_list("sku", flat=True):
        match = SKU_PATTERN.fullmatch(existing_sku)
        if match is not None:
            highest_existing = max(highest_existing, int(match.group(2)))

    sequence = sequences[category]
    sequence.last_value = max(sequence.last_value, highest_existing) + 1
    sequence.save(update_fields=("last_value",))
    return f"{prefix}{sequence.last_value:03d}"


def _unique_product_slug(name):
    base = slugify(name) or "product"
    candidate = base[:160]
    suffix = 2
    while Product.objects.filter(slug=candidate).exists():
        marker = f"-{suffix}"
        candidate = f"{base[:160 - len(marker)]}{marker}"
        suffix += 1
    return candidate


@transaction.atomic
def create_seedling_product(
    *, name, category, description, base_inventory_unit, is_active, is_published,
    sale_unit_name, sale_unit_base_quantity, price_amount, price_effective_start, actor
):
    """Create one canonical Product with its first sale unit and optional current KES price."""
    require_catalog_create(actor)
    name = (name or "").strip()
    category = (category or "").strip().upper()
    base_inventory_unit = (base_inventory_unit or "").strip().lower()
    sale_unit_name = (sale_unit_name or "").strip()
    if not name or not base_inventory_unit or not sale_unit_name:
        raise ValidationError("Product identity, base unit, and sale unit are required.")
    sku = _next_product_sku(category)
    slug = _unique_product_slug(name)

    product = Product(
        name=name,
        sku=sku,
        slug=slug,
        category=category,
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


@transaction.atomic
def edit_product(*, product_id, actor, name, description, category, is_active, is_published, base_inventory_unit=None):
    _require_permission(actor, "products.change_product")
    product = Product.objects.select_for_update().get(pk=product_id)
    if base_inventory_unit is not None:
        product.base_inventory_unit = base_inventory_unit.strip()
    for field, value in dict(name=name.strip(), description=description.strip(), category=category,
                             is_active=is_active, is_published=is_published).items():
        setattr(product, field, value)
    product.full_clean()
    product.save(update_fields=("name", "description", "category", "base_inventory_unit", "is_active", "is_published", "updated_at"))
    return product


@transaction.atomic
def edit_sale_unit(*, product_id, sale_unit_id, actor, name, base_quantity, is_active):
    require_catalog_view(actor)
    _require_permission(actor, "products.change_productsaleunit")
    Product.objects.select_for_update().get(pk=product_id)
    unit = ProductSaleUnit.objects.select_for_update().get(pk=sale_unit_id, product_id=product_id)
    unit.name, unit.base_quantity, unit.is_active = name, base_quantity, is_active
    unit.full_clean()
    unit.save(update_fields=("name", "base_quantity", "is_active", "updated_at"))
    return unit


@transaction.atomic
def add_product_price(*, sale_unit_id, actor, amount, effective_start, effective_end=None, is_active=True):
    _require_permission(actor, "products.add_productprice")
    unit = ProductSaleUnit.objects.select_for_update().get(pk=sale_unit_id)
    # Model validation rejects overlaps and preserves historical amounts/periods.
    price = ProductPrice(sale_unit=unit, amount=amount, effective_start=effective_start,
                         effective_end=effective_end, is_active=is_active)
    price.save()
    return price
