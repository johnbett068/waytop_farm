"""Future production capacity; deliberately independent of READY availability."""
from decimal import Decimal, ROUND_FLOOR, localcontext

from django.core.exceptions import ValidationError
from django.db import connection

from apps.commitments.models import Commitment
from apps.inventory.models import InventoryItem, InventoryLocation
from apps.products.models import ProductSaleUnit
from .models import ProductionBatch


def remaining_capacity(batch):
    # Sum exact persisted Decimals in Python: SQLite SUM uses floating point.
    with localcontext() as context:
        context.prec = 50
        booked = sum(Commitment.objects.filter(
            order_line__production_batch_id=batch.pk,
            order_line__supply_mode="PRE_ORDER", state=Commitment.State.ACTIVE,
        ).values_list("outstanding_base_quantity", flat=True), Decimal("0.000"))
        return max(Decimal("0.000"), batch.current_quantity - booked)


def bookable_units(*, batch, unit, location_id):
    if (
        batch.location_id != location_id or not location_id
        or batch.status != ProductionBatch.Status.IN_PRODUCTION
        or not batch.expected_ready_date or batch.current_quantity <= 0
        or not batch.product.is_active or not batch.product.is_published
        or unit.product_id != batch.product_id or not unit.is_active or unit.base_quantity <= 0
        or not InventoryLocation.objects.filter(pk=location_id, is_active=True, allows_saleable_stock=True).exists()
        or not InventoryItem.objects.filter(product_id=batch.product_id, kind="PRODUCT", is_active=True,
                                            base_unit=batch.product.base_inventory_unit).exists()
    ):
        return 0
    with localcontext() as context:
        context.prec = 50
        return int((remaining_capacity(batch) / unit.base_quantity).to_integral_value(rounding=ROUND_FLOOR))


def validate_booking_lines(*, lines, location_id, lock=False):
    """Lock batches before capacity reads; the locks also serialize audited decreases."""
    if lock and not connection.in_atomic_block:
        raise ValidationError("Booking capacity locking requires an atomic transaction.")
    if not lines or any(line.supply_mode != "PRE_ORDER" or not line.production_batch_id for line in lines):
        raise ValidationError("Bookings require only PRE_ORDER lines with a production batch.")
    query = ProductionBatch.objects.filter(pk__in={line.production_batch_id for line in lines}).order_by("pk")
    if lock:
        query = query.select_for_update()
    batches = {batch.pk: batch for batch in query}
    requested = {}
    with localcontext() as context:
        context.prec = 50
        for line in lines:
            batch = batches.get(line.production_batch_id)
            try:
                unit = ProductSaleUnit.objects.get(pk=line.sale_unit_id, product_id=line.product_id)
            except ProductSaleUnit.DoesNotExist as error:
                raise ValidationError("Booking Sale Unit is unavailable.") from error
            if batch is None or line.quantity <= 0 or line.quantity > bookable_units(batch=batch, unit=unit, location_id=location_id):
                raise ValidationError("Insufficient eligible production capacity at the selected Location.")
            # On confirmation, use the immutable conversion agreed on the Order Line.
            base = getattr(line, "base_quantity", unit.base_quantity)
            requested[batch.pk] = requested.get(batch.pk, Decimal("0.000")) + base * line.quantity
        for batch_id, required in requested.items():
            if required > remaining_capacity(batches[batch_id]):
                raise ValidationError("Combined Sale Units exceed remaining production capacity.")
    return batches
