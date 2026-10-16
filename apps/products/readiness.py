"""Catalog configuration diagnostics; deliberately independent of stock balances."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone
from apps.orders.services import _current_price


def product_readiness(product, *, at=None):
    at = at or timezone.now()
    reasons = []
    if not product.is_active:
        reasons.append("Product is inactive")
    if not product.is_published:
        reasons.append("Not published")
    try:
        item = product.inventory_item
    except ObjectDoesNotExist:
        item = None
    inventory = "Configured"
    if item is None:
        inventory = "Not configured"
        reasons.append("Missing inventory configuration; receive legitimate stock through Acquire Stock")
    elif not item.is_active or item.kind != "PRODUCT" or item.supply_id is not None:
        inventory = "Needs attention"
        reasons.append("Inventory configuration is inactive or invalid")
    elif not product.base_inventory_unit.strip() or item.base_unit != product.base_inventory_unit:
        inventory = "Needs attention"
        reasons.append("Inventory and Product stock units do not match")
    units = []
    for unit in product.sale_units.all():
        issues = []
        price = None
        if not unit.is_active:
            issues.append("Sale Unit is inactive")
        if unit.base_quantity <= 0:
            issues.append("Sale Unit conversion must be positive")
        try:
            price = _current_price(unit, at)
        except ValidationError:
            prices = list(unit.prices.all())
            active = [p for p in prices if p.is_active]
            current = [p for p in active if p.effective_start <= at and (p.effective_end is None or p.effective_end > at)]
            if len(current) > 1:
                issues.append("Multiple current prices; review pricing periods")
            elif current:
                issues.append("Price is zero or invalid")
            elif not prices:
                issues.append("Price not configured")
            elif not active:
                issues.append("No active price")
            else:
                if any(p.effective_start > at for p in active):
                    issues.append("Price not yet effective")
                if any(p.effective_end is not None and p.effective_end <= at for p in active):
                    issues.append("Price expired")
        units.append({"unit": unit, "price": price, "reasons": issues, "ready": not issues})
    if not any(u["unit"].is_active for u in units):
        reasons.append("No active Sale Unit")
    if not any(u["ready"] for u in units):
        reasons.extend(f'{u["unit"].name}: {reason}' for u in units for reason in u["reasons"])
    return {"ready": not reasons, "reasons": reasons, "units": units, "inventory": inventory}
