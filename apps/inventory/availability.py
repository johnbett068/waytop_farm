from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, localcontext

from django.db.models import Q, Sum
from django.utils import timezone

from apps.orders.models import OrderLine
from apps.products.models import Product, ProductSaleUnit

from .models import InventoryItem, StockLot, StockPosition


BASE_QUANTITY_QUANTUM = Decimal("0.001")


class AvailabilityUnavailable(Exception):
    """The requested availability cannot be represented truthfully."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class ReservationCoverage:
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class ReadyAvailability:
    """Customer-safe aggregate projection with no Inventory source details."""

    available_sale_units: int
    calculated_at: datetime
    reservation_coverage: str


class NoReservationPersistenceProvider:
    """Phase 1E-C boundary: no Reservation records can yet exist."""

    coverage = ReservationCoverage.NOT_IMPLEMENTED

    def active_ready_reserved_base_quantity(self, *, inventory_item, calculated_at):
        return Decimal("0.000")


class ActiveReservationProvider:
    """Authoritative Phase 1E-D aggregate of active READY Reservations."""

    coverage = ReservationCoverage.COMPLETE

    def active_ready_reserved_base_quantity(self, *, inventory_item, calculated_at):
        from .models import Reservation

        return (
            Reservation.objects.filter(
                inventory_item=inventory_item,
                state=Reservation.State.ACTIVE,
                remaining_base_quantity__gt=0,
            ).aggregate(total=Sum("remaining_base_quantity"))["total"]
            or Decimal("0.000")
        )


def _exact_non_negative_base_quantity(value, *, source):
    try:
        quantity = Decimal(str(value))
        quantized = quantity.quantize(BASE_QUANTITY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise AvailabilityUnavailable(
            "INVALID_QUANTITY_PROVIDER",
            f"{source} returned an invalid base quantity.",
        ) from error
    if not quantity.is_finite() or quantity < 0 or quantity != quantized:
        raise AvailabilityUnavailable(
            "INVALID_QUANTITY_PROVIDER",
            f"{source} did not return a non-negative exact Decimal(32,3) quantity.",
        )
    return quantized


def eligible_stock_positions(*, inventory_item, business_date):
    """Shared ratified eligibility query for Availability and Allocation."""
    return (
        StockPosition.objects.filter(
            item=inventory_item,
            item__is_active=True,
            location__is_active=True,
            location__allows_saleable_stock=True,
            lot__is_active=True,
            lot__condition=StockLot.Condition.SALEABLE,
            on_hand_base_quantity__gt=0,
        )
        .filter(Q(lot__expiry_date__isnull=True) | Q(lot__expiry_date__gte=business_date))
    )


def _eligible_physical_base_quantity(*, inventory_item, business_date):
    total = eligible_stock_positions(
        inventory_item=inventory_item,
        business_date=business_date,
    ).aggregate(total=Sum("on_hand_base_quantity"))["total"]
    return _exact_non_negative_base_quantity(
        total if total is not None else Decimal("0.000"),
        source="Inventory",
    )


def get_ready_availability(
    *,
    product,
    sale_unit,
    supply_mode=OrderLine.SupplyMode.READY,
    reservation_provider=None,
):
    """Calculate aggregate READY availability without exposing source details.

    Phase 1E-D uses persistent active Reservations by default. The injectable
    provider seam remains available for isolated provider-health tests without
    changing the customer-safe result shape.
    """
    if supply_mode != OrderLine.SupplyMode.READY:
        raise AvailabilityUnavailable(
            "PRE_ORDER_CAPACITY_UNAVAILABLE",
            "PRE_ORDER availability requires the future Production-capacity provider.",
        )
    if not isinstance(product, Product) or product.pk is None:
        raise AvailabilityUnavailable(
            "CATALOG_PRODUCT_UNAVAILABLE",
            "READY availability is available only for an active published Product.",
        )
    try:
        product = Product.objects.get(pk=product.pk, is_active=True, is_published=True)
    except Product.DoesNotExist as error:
        raise AvailabilityUnavailable(
            "CATALOG_PRODUCT_UNAVAILABLE",
            "READY availability is available only for an active published Product.",
        ) from error
    if not isinstance(sale_unit, ProductSaleUnit) or sale_unit.pk is None:
        raise AvailabilityUnavailable(
            "CATALOG_SALE_UNIT_UNAVAILABLE",
            "READY availability requires an active Sale Unit for the Product.",
        )
    try:
        sale_unit = ProductSaleUnit.objects.get(
            pk=sale_unit.pk,
            product=product,
            is_active=True,
        )
    except ProductSaleUnit.DoesNotExist as error:
        raise AvailabilityUnavailable(
            "CATALOG_SALE_UNIT_UNAVAILABLE",
            "READY availability requires an active Sale Unit for the Product.",
        ) from error
    try:
        inventory_item = InventoryItem.objects.select_related("product").get(product=product)
    except InventoryItem.DoesNotExist as error:
        raise AvailabilityUnavailable(
            "INVENTORY_PROVIDER_UNAVAILABLE",
            "The Product has no authoritative Inventory Item.",
        ) from error
    if inventory_item.base_unit != product.base_inventory_unit:
        raise AvailabilityUnavailable(
            "INVENTORY_PROVIDER_UNHEALTHY",
            "Inventory Item and Product base units do not agree.",
        )

    calculated_at = timezone.now()
    business_date = timezone.localdate(calculated_at)
    eligible_base = _eligible_physical_base_quantity(
        inventory_item=inventory_item,
        business_date=business_date,
    )
    provider = reservation_provider or ActiveReservationProvider()
    if not hasattr(provider, "active_ready_reserved_base_quantity") or not hasattr(
        provider, "coverage"
    ):
        raise AvailabilityUnavailable(
            "RESERVATION_PROVIDER_UNAVAILABLE",
            "The READY Reservation provider is unavailable.",
        )
    reserved_base = _exact_non_negative_base_quantity(
        provider.active_ready_reserved_base_quantity(
            inventory_item=inventory_item,
            calculated_at=calculated_at,
        ),
        source="Reservation",
    )
    if reserved_base > eligible_base:
        raise AvailabilityUnavailable(
            "RESERVATION_INVARIANT_VIOLATION",
            "Active READY Reservations exceed eligible physical Inventory.",
        )

    sale_unit_base = _exact_non_negative_base_quantity(
        sale_unit.base_quantity,
        source="Catalog Sale Unit",
    )
    if sale_unit_base == 0:
        raise AvailabilityUnavailable(
            "CATALOG_SALE_UNIT_UNAVAILABLE",
            "Sale Unit base quantity must be positive.",
        )
    available_base = eligible_base - reserved_base
    with localcontext() as context:
        context.prec = 50
        available_sale_units = int(
            (available_base / sale_unit_base).to_integral_value(rounding=ROUND_FLOOR)
        )
    return ReadyAvailability(
        available_sale_units=available_sale_units,
        calculated_at=calculated_at,
        reservation_coverage=provider.coverage,
    )
