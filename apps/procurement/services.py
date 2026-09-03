import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.idempotency import lock_idempotency_key
from apps.inventory.models import (
    InventoryItem, InventoryLocation, InventoryMovement, StockLot,
)
from apps.inventory.services import MovementLineInput, post_inventory_movement

from .models import (
    GoodsReceiptLine, PurchaseOrderEvent, Supplier, SupplierEvent,
    SupplierGoodsReceipt, SupplierPurchaseOrder, SupplierPurchaseOrderLine,
)


@dataclass(frozen=True)
class PurchaseLineInput:
    supply_id: uuid.UUID
    ordered_quantity: Decimal
    purchase_unit: str
    base_quantity_per_purchase_unit: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class ReceiptLineInput:
    purchase_order_line_id: uuid.UUID
    accepted_base_quantity: Decimal
    rejected_base_quantity: Decimal
    rejection_reason: str
    lot_code: str
    destination_location_id: uuid.UUID


def _require(actor, permission):
    if (
        actor is None or not actor.is_authenticated or not actor.is_active
        or not actor.is_staff or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Supplier Inventory operation requires {permission}.")


def require_procurement_view(actor): _require(actor, "procurement.view")


def _fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _decimal(value, field, quantum, *, positive=False, non_negative=False):
    try:
        raw = Decimal(str(value))
        normalized = raw.quantize(quantum)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({field: "Enter a valid decimal value."}) from error
    if not raw.is_finite() or raw != normalized:
        raise ValidationError({field: f"Use at most {abs(quantum.as_tuple().exponent)} decimal places."})
    if positive and normalized <= 0:
        raise ValidationError({field: "Value must be positive."})
    if non_negative and normalized < 0:
        raise ValidationError({field: "Value cannot be negative."})
    return normalized


@transaction.atomic
def save_supplier(
    *, supplier_id=None, code, name, contact_person="", phone="", email="", address="",
    notes="", is_active=True, actor, reason, correlation_id, idempotency_key,
):
    _require(actor, "procurement.manage_suppliers")
    idempotency_key = lock_idempotency_key(idempotency_key)
    operation = SupplierEvent.Operation.CREATED if supplier_id is None else SupplierEvent.Operation.UPDATED
    values = {
        "supplier": str(supplier_id) if supplier_id else None,
        "code": (code or "").strip().upper(), "name": (name or "").strip(),
        "contact_person": (contact_person or "").strip(), "phone": (phone or "").strip(),
        "email": (email or "").strip().lower(), "address": (address or "").strip(),
        "notes": (notes or "").strip(), "is_active": bool(is_active),
        "actor": str(actor.pk), "reason": (reason or "").strip(),
        "correlation": str(correlation_id), "operation": operation,
    }
    fingerprint = _fingerprint(values)
    existing = SupplierEvent.objects.select_related("supplier").filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("Supplier idempotency key was reused with different input.")
        return existing.supplier
    if not values["reason"]: raise ValidationError({"reason": "A Supplier change reason is required."})
    if supplier_id:
        supplier = Supplier.objects.select_for_update().get(pk=supplier_id)
        if values["code"] != supplier.code:
            raise ValidationError({"code": "Supplier code is immutable."})
        if supplier.is_active and not values["is_active"]:
            operation = SupplierEvent.Operation.DEACTIVATED
        supplier.name = values["name"]
        supplier.contact_person = values["contact_person"]
        supplier.phone = values["phone"]
        supplier.email = values["email"]
        supplier.address = values["address"]
        supplier.notes = values["notes"]
        supplier.is_active = values["is_active"]
    else:
        supplier = Supplier(
            code=values["code"], name=values["name"], contact_person=values["contact_person"],
            phone=values["phone"], email=values["email"], address=values["address"],
            notes=values["notes"], is_active=values["is_active"],
        )
    supplier.save(_procurement_service_write=True)
    SupplierEvent(
        supplier=supplier, operation=operation, actor=actor, reason=values["reason"],
        correlation_id=correlation_id, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_procurement_service_write=True)
    return supplier


@transaction.atomic
def create_purchase_order(
    *, number, supplier_id, order_date, expected_date, reference, notes, lines,
    actor, reason, correlation_id, idempotency_key,
):
    _require(actor, "procurement.manage_purchases")
    idempotency_key = lock_idempotency_key(idempotency_key)
    normalized = []
    for line in lines:
        ordered = _decimal(line.ordered_quantity, "ordered_quantity", Decimal("0.001"), positive=True)
        conversion = _decimal(line.base_quantity_per_purchase_unit, "base_quantity_per_purchase_unit", Decimal("0.001"), positive=True)
        cost = _decimal(line.unit_cost, "unit_cost", Decimal("0.01"), non_negative=True)
        normalized.append((line, ordered, conversion, cost))
    if not normalized: raise ValidationError("A Purchase Order requires at least one line.")
    payload = {
        "number": (number or "").strip().upper(), "supplier": str(supplier_id),
        "order_date": order_date.isoformat(), "expected_date": expected_date.isoformat() if expected_date else None,
        "reference": (reference or "").strip(), "notes": (notes or "").strip(),
        "lines": [{"supply": str(v[0].supply_id), "quantity": format(v[1], "f"),
                   "unit": (v[0].purchase_unit or "").strip().lower(),
                   "conversion": format(v[2], "f"), "cost": format(v[3], "f")} for v in normalized],
        "actor": str(actor.pk), "reason": (reason or "").strip(), "correlation": str(correlation_id),
    }
    fingerprint = _fingerprint(payload)
    existing = PurchaseOrderEvent.objects.select_related("purchase_order").filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.request_fingerprint != fingerprint: raise ValidationError("Purchase Order key was reused with different input.")
        return existing.purchase_order
    if not payload["reason"]: raise ValidationError({"reason": "A Purchase Order reason is required."})
    supplier = Supplier.objects.select_for_update().get(pk=supplier_id, is_active=True)
    supply_ids = [v[0].supply_id for v in normalized]
    items = {item.supply_id: item for item in InventoryItem.objects.select_for_update(of=("self",)).select_related("supply").filter(
        kind=InventoryItem.Kind.SUPPLY, supply_id__in=supply_ids, supply__is_active=True
    )}
    if set(items) != set(supply_ids): raise ValidationError("Every Purchase Order line requires an active Inventory Supply.")
    po = SupplierPurchaseOrder(
        number=payload["number"], supplier=supplier, order_date=order_date,
        expected_date=expected_date, reference=payload["reference"], notes=payload["notes"],
        created_by=actor,
    )
    po.save(_procurement_service_write=True)
    for index, (line, ordered, conversion, cost) in enumerate(normalized, 1):
        supply = items[line.supply_id].supply
        raw_ordered_base = ordered * conversion
        ordered_base = raw_ordered_base.quantize(Decimal("0.001"))
        if raw_ordered_base != ordered_base:
            raise ValidationError("Purchase conversion produces more than three base-quantity decimals.")
        if not supply.allows_fractional_quantity and ordered_base != ordered_base.to_integral_value():
            raise ValidationError("A discrete Supply requires a whole ordered base quantity.")
        SupplierPurchaseOrderLine(
            purchase_order=po, line_number=index, supply=supply,
            supply_code=supply.code, supply_name=supply.name,
            purchase_unit=(line.purchase_unit or "").strip().lower(),
            ordered_quantity=ordered, base_quantity_per_purchase_unit=conversion,
            ordered_base_quantity=ordered_base, unit_cost=cost,
            line_total=(ordered * cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN),
        ).save(_procurement_service_write=True)
    PurchaseOrderEvent(
        purchase_order=po, operation=PurchaseOrderEvent.Operation.CREATED,
        previous_status="", new_status=po.status, actor=actor, reason=payload["reason"],
        correlation_id=correlation_id, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_procurement_service_write=True)
    return po


@transaction.atomic
def transition_purchase_order(*, purchase_order_id, to_status, actor, reason, correlation_id, idempotency_key):
    _require(actor, "procurement.manage_purchases")
    idempotency_key = lock_idempotency_key(idempotency_key)
    payload = {"po": str(purchase_order_id), "to": to_status, "actor": str(actor.pk),
               "reason": (reason or "").strip(), "correlation": str(correlation_id)}
    fingerprint = _fingerprint(payload)
    existing = PurchaseOrderEvent.objects.select_related("purchase_order").filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.request_fingerprint != fingerprint: raise ValidationError("Purchase transition key was reused with different input.")
        return existing.purchase_order
    po = SupplierPurchaseOrder.objects.select_for_update().get(pk=purchase_order_id)
    allowed = {
        SupplierPurchaseOrder.Status.DRAFT: {SupplierPurchaseOrder.Status.ORDERED, SupplierPurchaseOrder.Status.CANCELLED},
        SupplierPurchaseOrder.Status.ORDERED: {SupplierPurchaseOrder.Status.CANCELLED},
    }
    if to_status not in allowed.get(po.status, set()): raise ValidationError("Purchase Order transition is not allowed.")
    if not payload["reason"]: raise ValidationError({"reason": "A transition reason is required."})
    previous = po.status
    po.status = to_status
    po.save(_procurement_service_write=True)
    operation = PurchaseOrderEvent.Operation.PLACED if to_status == SupplierPurchaseOrder.Status.ORDERED else PurchaseOrderEvent.Operation.CANCELLED
    PurchaseOrderEvent(
        purchase_order=po, operation=operation, previous_status=previous, new_status=to_status,
        actor=actor, reason=payload["reason"], correlation_id=correlation_id,
        idempotency_key=idempotency_key, request_fingerprint=fingerprint,
    ).save(_procurement_service_write=True)
    return po


@transaction.atomic
def post_goods_receipt(
    *, number, purchase_order_id, delivery_note_reference, receipt_date, lines,
    actor, reason, correlation_id, idempotency_key,
):
    _require(actor, "inventory.receive")
    idempotency_key = lock_idempotency_key(idempotency_key)
    normalized = []
    for line in lines:
        accepted = _decimal(line.accepted_base_quantity, "accepted_base_quantity", Decimal("0.001"), non_negative=True)
        rejected = _decimal(line.rejected_base_quantity, "rejected_base_quantity", Decimal("0.001"), non_negative=True)
        if accepted == 0 and rejected == 0: raise ValidationError("Each receipt line requires accepted or rejected quantity.")
        normalized.append((line, accepted, rejected))
    if not normalized or not any(accepted > 0 for _, accepted, _ in normalized):
        raise ValidationError("A posted Goods Receipt requires accepted physical stock.")
    payload = {
        "number": (number or "").strip().upper(), "po": str(purchase_order_id),
        "delivery_note": (delivery_note_reference or "").strip(), "date": receipt_date.isoformat(),
        "lines": [{"po_line": str(v[0].purchase_order_line_id), "accepted": format(v[1], "f"),
                   "rejected": format(v[2], "f"), "rejection_reason": (v[0].rejection_reason or "").strip(),
                   "lot": (v[0].lot_code or "").strip(), "location": str(v[0].destination_location_id)} for v in normalized],
        "actor": str(actor.pk), "reason": (reason or "").strip(), "correlation": str(correlation_id),
    }
    fingerprint = _fingerprint(payload)
    existing = SupplierGoodsReceipt.objects.select_related("movement").filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.request_fingerprint != fingerprint: raise ValidationError("Goods Receipt key was reused with different input.")
        return existing
    if not payload["delivery_note"] or not payload["reason"]:
        raise ValidationError("Delivery note reference and receipt reason are required.")
    po = SupplierPurchaseOrder.objects.select_for_update().select_related("supplier").get(pk=purchase_order_id)
    if po.status not in (SupplierPurchaseOrder.Status.ORDERED, SupplierPurchaseOrder.Status.PARTIALLY_RECEIVED):
        raise ValidationError("Only an ordered Purchase Order can be received.")
    po_lines = {line.pk: line for line in SupplierPurchaseOrderLine.objects.select_for_update(of=("self",)).select_related(
        "supply__inventory_item"
    ).filter(purchase_order=po).order_by("line_number")}
    requested_ids = [line.purchase_order_line_id for line, _, _ in normalized]
    if len(set(requested_ids)) != len(requested_ids) or not set(requested_ids) <= set(po_lines):
        raise ValidationError("Goods Receipt lines must uniquely belong to the selected Purchase Order.")
    location_ids = {line.destination_location_id for line, _, _ in normalized}
    locations = {location.pk: location for location in InventoryLocation.objects.select_for_update().filter(
        pk__in=location_ids, is_active=True
    )}
    if set(locations) != location_ids: raise ValidationError("Goods Receipt requires active Inventory locations.")
    item_ids = {po_lines[line_id].supply.inventory_item.pk for line_id in requested_ids}
    items = {item.pk: item for item in InventoryItem.objects.select_for_update(of=("self",)).select_related("supply").filter(
        pk__in=item_ids, kind=InventoryItem.Kind.SUPPLY, is_active=True
    )}
    lots = {}
    movement_inputs = []
    accepted_rows = []
    for input_line, accepted, rejected in normalized:
        po_line = po_lines[input_line.purchase_order_line_id]
        item = items[po_line.supply.inventory_item.pk]
        if po_line.received_base_quantity + accepted > po_line.ordered_base_quantity:
            raise ValidationError("Accepted receipt quantity cannot exceed the ordered base quantity.")
        if not item.supply.allows_fractional_quantity and (
            accepted != accepted.to_integral_value() or rejected != rejected.to_integral_value()
        ):
            raise ValidationError("A discrete Supply requires whole receipt quantities.")
        rejection_reason = (input_line.rejection_reason or "").strip()
        if rejected > 0 and not rejection_reason: raise ValidationError("Rejected quantity requires a reason.")
        lot_code = (input_line.lot_code or "").strip()
        if not lot_code: raise ValidationError("A Goods Receipt lot code is required.")
        lot, _created = StockLot.objects.get_or_create(
            item=item, lot_code=lot_code,
            defaults={"condition": StockLot.Condition.SALEABLE,
                      "provenance_reference": payload["delivery_note"],
                      "provenance_note": f"Supplier {po.supplier.code}; Purchase Order {po.number}"},
        )
        lots[input_line.purchase_order_line_id] = lot
        if accepted > 0:
            movement_inputs.append(MovementLineInput(
                item_id=item.pk, lot_id=lot.pk, quantity=accepted,
                destination_location_id=input_line.destination_location_id,
            ))
            accepted_rows.append(input_line.purchase_order_line_id)
    movement = post_inventory_movement(
        movement_type=InventoryMovement.Type.RECEIPT, lines=tuple(movement_inputs),
        actor=actor, reason=payload["reason"], idempotency_key=idempotency_key,
        correlation_id=correlation_id, source_type="SUPPLIER_GOODS_RECEIPT",
        source_reference=payload["number"],
    )
    receipt = SupplierGoodsReceipt(
        number=payload["number"], purchase_order=po,
        delivery_note_reference=payload["delivery_note"], receipt_date=receipt_date,
        movement=movement, received_by=actor, reason=payload["reason"],
        correlation_id=correlation_id, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    receipt.save(_procurement_service_write=True)
    movement_lines = iter(movement.lines.order_by("line_number"))
    for index, (input_line, accepted, rejected) in enumerate(normalized, 1):
        po_line = po_lines[input_line.purchase_order_line_id]
        linked_movement_line = next(movement_lines) if accepted > 0 else None
        GoodsReceiptLine(
            receipt=receipt, line_number=index, purchase_order_line=po_line,
            movement_line=linked_movement_line, stock_lot=lots[po_line.pk],
            destination_location_id=input_line.destination_location_id,
            accepted_base_quantity=accepted, rejected_base_quantity=rejected,
            rejection_reason=(input_line.rejection_reason or "").strip(),
        ).save(_procurement_service_write=True)
        po_line.received_base_quantity += accepted
        po_line.rejected_base_quantity += rejected
        po_line.save(_procurement_service_write=True)
    previous = po.status
    all_received = all(line.received_base_quantity >= line.ordered_base_quantity for line in po_lines.values())
    po.status = SupplierPurchaseOrder.Status.RECEIVED if all_received else SupplierPurchaseOrder.Status.PARTIALLY_RECEIVED
    po.save(_procurement_service_write=True)
    PurchaseOrderEvent(
        purchase_order=po, operation=PurchaseOrderEvent.Operation.RECEIPT_POSTED,
        previous_status=previous, new_status=po.status, actor=actor, reason=payload["reason"],
        correlation_id=correlation_id, idempotency_key=uuid.uuid5(idempotency_key, "purchase-order-receipt-event"),
        request_fingerprint=fingerprint,
    ).save(_procurement_service_write=True)
    return receipt
