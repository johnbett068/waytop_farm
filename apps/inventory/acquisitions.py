import hashlib
import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key
from apps.procurement.models import Supplier
from apps.products.models import Product

from .models import (
    ExternalStockAcquisition,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    StockLot,
)
from .services import MovementLineInput, _require_permission, post_inventory_movement


def _decimal(value, field_name, quantum, *, non_negative=False, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({field_name: "Enter a valid decimal value."}) from error
    if not result.is_finite() or (positive and result <= 0) or (non_negative and result < 0):
        qualifier = "positive" if positive else "zero or greater"
        raise ValidationError({field_name: f"This value must be finite and {qualifier}."})
    try:
        normalized = result.quantize(quantum)
    except InvalidOperation as error:
        raise ValidationError({field_name: "This value exceeds the supported precision."}) from error
    if result != normalized:
        raise ValidationError({field_name: f"Use at most {abs(quantum.as_tuple().exponent)} decimal places."})
    return normalized


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@transaction.atomic
def acquire_external_stock(
    *, product_id, quantity, unit_cost, acquisition_date, location_id, condition,
    actor, correlation_id, idempotency_key, supplier_id=None, reference="", note="",
    supplier_batch_reference="",
):
    """Record acquisition evidence and post its product receipt atomically."""
    _require_permission(actor, "inventory.receive")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    product_id = _uuid(product_id, "product_id")
    location_id = _uuid(location_id, "location_id")
    supplier_id = _uuid(supplier_id, "supplier_id") if supplier_id else None
    quantity = _decimal(quantity, "quantity", Decimal("0.001"), positive=True)
    unit_cost = _decimal(unit_cost, "unit_cost", Decimal("0.01"), non_negative=True)
    if not isinstance(acquisition_date, date):
        raise ValidationError({"acquisition_date": "Enter a valid acquisition date."})
    lot_code = f"WTP-LOT-{idempotency_key.hex.upper()}"
    supplier_batch_reference = (supplier_batch_reference or "").strip()
    reference = (reference or "").strip()
    note = (note or "").strip()
    if condition not in StockLot.Condition.values:
        raise ValidationError({"condition": "Select a valid Inventory lot condition."})

    payload = {
        "product": str(product_id),
        "quantity": format(quantity, "f"),
        "unit_cost": format(unit_cost, "f"),
        "acquisition_date": acquisition_date.isoformat(),
        "supplier": str(supplier_id) if supplier_id else None,
        "location": str(location_id),
        "lot_code": lot_code,
        "supplier_batch_reference": supplier_batch_reference,
        "condition": condition,
        "reference": reference,
        "note": note,
        "actor": str(actor.pk) if actor is not None else None,
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint(payload)
    existing = ExternalStockAcquisition.objects.select_related("movement").filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("Acquisition idempotency key was reused with different input.")
        return existing

    product = Product.objects.select_for_update().filter(pk=product_id, is_active=True).first()
    if product is None:
        raise ValidationError({"product": "Select an active Product."})
    # Catalog creation is stock-free. Introduce the canonical one-to-one item
    # only inside the receipt transaction, using the Product's existing unit.
    item, _created = InventoryItem.objects.select_for_update(of=("self",)).get_or_create(
        product=product,
        defaults={"kind": InventoryItem.Kind.PRODUCT, "base_unit": product.base_inventory_unit},
    )
    if not item.is_active or item.kind != InventoryItem.Kind.PRODUCT:
        raise ValidationError({"product": "The Product's Inventory Item must be active."})
    location = InventoryLocation.objects.select_for_update().get(pk=location_id, is_active=True)
    supplier = None
    if supplier_id:
        supplier = Supplier.objects.select_for_update().filter(pk=supplier_id).first()
        if supplier is None:
            raise ValidationError({"supplier": "Select an existing Supplier."})

    acquisition_id = uuid.uuid5(idempotency_key, "external-stock-acquisition")
    provenance_reference = reference or str(acquisition_id)
    provenance_note = "External stock acquisition"
    lot = StockLot.objects.create(
        item=item,
        lot_code=lot_code,
        condition=condition,
        provenance_reference=provenance_reference,
        provenance_note=provenance_note,
    )
    effective_at = timezone.make_aware(
        datetime.combine(acquisition_date, time.min), timezone.get_current_timezone()
    )
    movement = post_inventory_movement(
        movement_type=InventoryMovement.Type.RECEIPT,
        lines=(MovementLineInput(
            item_id=item.pk,
            lot_id=lot.pk,
            quantity=quantity,
            destination_location_id=location.pk,
        ),),
        actor=actor,
        reason=note or f"External stock acquisition: {item.product.name}",
        idempotency_key=idempotency_key,
        source_type="EXTERNAL_STOCK_ACQUISITION",
        source_reference=str(acquisition_id),
        correlation_id=correlation_id,
        effective_at=effective_at,
    )
    acquisition = ExternalStockAcquisition(
        id=acquisition_id,
        movement=movement,
        movement_line=movement.lines.get(),
        supplier=supplier,
        supplier_batch_reference=supplier_batch_reference,
        acquisition_date=acquisition_date,
        unit_cost=unit_cost,
        reference=reference,
        note=note,
        acquired_by=actor,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    acquisition.save(_stock_acquisition_service_write=True)
    return acquisition
