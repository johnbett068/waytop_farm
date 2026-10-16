from django.db.models import Prefetch, Q
from django.urls import reverse
from django.utils import timezone

from .models import Product, ProductPrice, ProductSaleUnit, ProductImage


def public_catalog_products(*, search=None, at=None, limit=None):
    """Return the public catalog projection with only current commercial data."""
    at = at or timezone.now()
    current_prices = ProductPrice.objects.filter(
        is_active=True,
        effective_start__lte=at,
    ).filter(Q(effective_end__isnull=True) | Q(effective_end__gt=at))
    active_units = ProductSaleUnit.objects.filter(is_active=True).prefetch_related(
        Prefetch("prices", queryset=current_prices, to_attr="applicable_prices")
    )
    products = Product.objects.filter(is_active=True, is_published=True).prefetch_related(
        Prefetch("sale_units", queryset=active_units, to_attr="catalog_sale_units"),
        Prefetch("images", queryset=ProductImage.objects.all(), to_attr="ordered_image_records")
    )
    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(description__icontains=search) | Q(sku__icontains=search)
        )
    if limit is not None:
        products = products[:limit]

    result = list(products)
    for product in result:
        product.catalog_images = [{"url": record.display_url, "alt": record.alt_text or product.name}
                                  for record in product.ordered_image_records]
        product.catalog_main_image = product.catalog_images[0] if product.catalog_images else None
        prices = []
        for sale_unit in product.catalog_sale_units:
            sale_unit.catalog_price = sale_unit.applicable_prices[0] if sale_unit.applicable_prices else None
            if sale_unit.catalog_price is not None:
                prices.append(sale_unit.catalog_price.amount)
        product.catalog_lowest_price = min(prices) if prices else None
    return result


def commerce_catalog_projection(products):
    """Serialize only public product identity and currently priced sale units."""
    projection = []
    for product in products:
        sale_units = []
        for sale_unit in product.catalog_sale_units:
            price = sale_unit.catalog_price
            if price is None:
                continue
            sale_units.append(
                {
                    "key": f"{product.slug}:{sale_unit.pk}",
                    "name": sale_unit.name,
                    "base_quantity": format(sale_unit.base_quantity, "f"),
                    "base_unit": product.base_inventory_unit,
                    "amount": format(price.amount, "f"),
                    "currency": price.currency,
                }
            )
        projection.append(
            {
                "slug": product.slug,
                "name": product.name,
                "description": product.description,
                "product_url": reverse("products:product_detail", args=(product.slug,)),
                "sale_units": sale_units,
                "main_image": product.catalog_main_image if product.catalog_main_image and product.catalog_main_image["url"] else None,
            }
        )
    return projection
