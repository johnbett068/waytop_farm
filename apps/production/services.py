import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.idempotency import lock_idempotency_key
from apps.products.models import Product

from .models import (
    NurseryActivity,
    ProductionBatch,
    ProductionBatchEvent,
    ProductionLabour,
    ProductionPurchase,
)


QUANTITY_QUANTUM = Decimal("0.001")
EFFORT_QUANTUM = Decimal("0.01")
MONEY_QUANTUM = Decimal("0.01")
LEGAL_TRANSITIONS = {
    ProductionBatch.Status.PLANNED: ProductionBatch.Status.IN_PRODUCTION,
    ProductionBatch.Status.IN_PRODUCTION: ProductionBatch.Status.READY,
    ProductionBatch.Status.READY: ProductionBatch.Status.CLOSED,
}


def _require_permission(actor, permission):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Production operation requires {permission}.")


def require_view_permission(actor):
    _require_permission(actor, "production.view_operations")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _decimal(value, field_name, quantum, *, positive=False, non_negative=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({field_name: "Enter a valid decimal value."}) from error
    if not number.is_finite():
        raise ValidationError({field_name: "Value must be finite."})
    if positive and number <= 0:
        raise ValidationError({field_name: "Value must be positive."})
    if non_negative and number < 0:
        raise ValidationError({field_name: "Value cannot be negative."})
    try:
        normalized = number.quantize(quantum)
    except InvalidOperation as error:
        raise ValidationError({field_name: "Value exceeds supported precision."}) from error
    if normalized != number:
        raise ValidationError(
            {field_name: f"Value supports at most {abs(quantum.as_tuple().exponent)} decimal places."}
        )
    return normalized


def _money_total(quantity, rate):
    total = (quantity * rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
    if total.adjusted() + 1 > 14:
        raise ValidationError("Calculated total cost exceeds supported precision.")
    return total


def _text(value, field_name, *, required=True, max_length=None):
    normalized = (value or "").strip()
    if required and not normalized:
        raise ValidationError({field_name: "This field is required."})
    if max_length and len(normalized) > max_length:
        raise ValidationError({field_name: f"Ensure this value has at most {max_length} characters."})
    return normalized


def _fingerprint(operation, payload):
    encoded = json.dumps(
        {"operation": operation, **payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_retry(idempotency_key, fingerprint, operation):
    event = ProductionBatchEvent.objects.filter(idempotency_key=idempotency_key).first()
    if event is None:
        return None
    if event.request_fingerprint != fingerprint or event.operation != operation:
        raise ValidationError("Production idempotency key was reused with different input.")
    return event.batch


@transaction.atomic
def create_batch(
    *, batch_number, product_id, start_date, expected_ready_date, quantity_started,
    notes, actor, correlation_id, idempotency_key, location_id=None
):
    _require_permission(actor, "production.manage_batches")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    batch_number = _text(batch_number, "batch_number", max_length=64).upper()
    quantity_started = _decimal(
        quantity_started, "quantity_started", QUANTITY_QUANTUM, positive=True
    )
    product_id = _uuid(product_id, "product_id")
    location_id = _booking_location(location_id)
    payload = {
        "batch_number": batch_number,
        "product_id": str(product_id),
        "location_id": str(location_id) if location_id else None,
        "start_date": start_date.isoformat(),
        "expected_ready_date": expected_ready_date.isoformat(),
        "quantity_started": format(quantity_started, "f"),
        "notes": (notes or "").strip(),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint(ProductionBatchEvent.Operation.CREATED, payload)
    retry = _event_retry(idempotency_key, fingerprint, ProductionBatchEvent.Operation.CREATED)
    if retry:
        return retry
    product = Product.objects.select_for_update().get(pk=product_id)
    if not product.is_active:
        raise ValidationError({"product_id": "Only active seedling Products may be used."})
    if expected_ready_date < start_date:
        raise ValidationError({"expected_ready_date": "Expected ready date cannot precede start date."})
    batch = ProductionBatch(
        location_id=location_id,
        batch_number=batch_number,
        product=product,
        start_date=start_date,
        expected_ready_date=expected_ready_date,
        quantity_started=quantity_started,
        current_quantity=quantity_started,
        status=ProductionBatch.Status.PLANNED,
        notes=(notes or "").strip(),
        created_by=actor,
    )
    batch.save(_production_service_write=True)
    ProductionBatchEvent(
        batch=batch,
        operation=ProductionBatchEvent.Operation.CREATED,
        actor=actor,
        reason="Batch created.",
        to_status=batch.status,
        location_id=batch.location_id,
        current_quantity=batch.current_quantity,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_production_service_write=True)
    return batch


@transaction.atomic
def update_batch(
    *, batch_id, current_quantity, expected_ready_date, notes, reason, actor,
    correlation_id, idempotency_key, location_id=None
):
    _require_permission(actor, "production.manage_batches")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    batch_id = _uuid(batch_id, "batch_id")
    current_quantity = _decimal(
        current_quantity, "current_quantity", QUANTITY_QUANTUM, non_negative=True
    )
    reason = _text(reason, "reason")
    location_id = _booking_location(location_id)
    payload = {
        "batch_id": str(batch_id),
        "current_quantity": format(current_quantity, "f"),
        "location_id": str(location_id) if location_id else None,
        "expected_ready_date": expected_ready_date.isoformat(),
        "notes": (notes or "").strip(),
        "reason": reason,
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint(ProductionBatchEvent.Operation.UPDATED, payload)
    retry = _event_retry(idempotency_key, fingerprint, ProductionBatchEvent.Operation.UPDATED)
    if retry:
        return retry
    batch = ProductionBatch.objects.select_for_update().get(pk=batch_id)
    if batch.status == ProductionBatch.Status.CLOSED:
        raise ValidationError("Closed Production batches cannot be changed.")
    if current_quantity > batch.current_quantity:
        raise ValidationError({"current_quantity": "Current quantity may only decrease."})
    if expected_ready_date < batch.start_date:
        raise ValidationError({"expected_ready_date": "Expected ready date cannot precede start date."})
    previous_quantity = batch.current_quantity
    previous_location_id = batch.location_id
    if location_id is not None and location_id != batch.location_id:
        if batch.booking_lines.exists():
            raise ValidationError("A batch referenced by bookings cannot change Location.")
        batch.location_id = location_id
    batch.current_quantity = current_quantity
    batch.expected_ready_date = expected_ready_date
    batch.notes = (notes or "").strip()
    batch.save(_production_service_write=True)
    ProductionBatchEvent(
        batch=batch,
        operation=ProductionBatchEvent.Operation.UPDATED,
        actor=actor,
        reason=reason,
        from_status=batch.status,
        to_status=batch.status,
        previous_quantity=previous_quantity,
        previous_location_id=previous_location_id,
        location_id=batch.location_id,
        current_quantity=batch.current_quantity,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_production_service_write=True)
    return batch


@transaction.atomic
def transition_batch(
    *, batch_id, to_status, reason, actor, correlation_id, idempotency_key
):
    _require_permission(actor, "production.manage_batches")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    batch_id = _uuid(batch_id, "batch_id")
    reason = _text(reason, "reason")
    if to_status not in ProductionBatch.Status.values:
        raise ValidationError({"to_status": "Unknown Production batch status."})
    payload = {
        "batch_id": str(batch_id),
        "to_status": to_status,
        "reason": reason,
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint(ProductionBatchEvent.Operation.TRANSITIONED, payload)
    retry = _event_retry(idempotency_key, fingerprint, ProductionBatchEvent.Operation.TRANSITIONED)
    if retry:
        return retry
    batch = ProductionBatch.objects.select_for_update().get(pk=batch_id)
    expected = LEGAL_TRANSITIONS.get(batch.status)
    if to_status != expected:
        raise ValidationError(
            f"Cannot transition Production batch from {batch.status} to {to_status}."
        )
    if to_status == ProductionBatch.Status.READY and batch.current_quantity <= 0:
        raise ValidationError("A Production batch must have current quantity before becoming READY.")
    previous = batch.status
    batch.status = to_status
    batch.save(_production_service_write=True)
    ProductionBatchEvent(
        batch=batch,
        operation=ProductionBatchEvent.Operation.TRANSITIONED,
        actor=actor,
        reason=reason,
        from_status=previous,
        to_status=to_status,
        previous_quantity=batch.current_quantity,
        current_quantity=batch.current_quantity,
        previous_location_id=batch.location_id,
        location_id=batch.location_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    ).save(_production_service_write=True)
    return batch


def _record_retry(model, idempotency_key, fingerprint):
    record = model.objects.filter(idempotency_key=idempotency_key).first()
    if record is not None and record.request_fingerprint != fingerprint:
        raise ValidationError("Production idempotency key was reused with different input.")
    return record


def _optional_batch(batch_id):
    if not batch_id:
        return None
    batch = ProductionBatch.objects.select_for_update().get(pk=_uuid(batch_id, "batch_id"))
    if batch.status == ProductionBatch.Status.CLOSED:
        raise ValidationError("Closed Production batches cannot receive new operational records.")
    return batch


@transaction.atomic
def record_purchase(
    *, purchase_date, supplier, item_description, category, quantity, unit, unit_cost,
    batch_id, reference, notes, actor, correlation_id, idempotency_key
):
    _require_permission(actor, "production.record_purchases")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    quantity = _decimal(quantity, "quantity", QUANTITY_QUANTUM, positive=True)
    unit_cost = _decimal(unit_cost, "unit_cost", MONEY_QUANTUM, non_negative=True)
    values = {
        "purchase_date": purchase_date,
        "supplier": _text(supplier, "supplier", max_length=200),
        "item_description": _text(item_description, "item_description", max_length=250),
        "category": category,
        "quantity": quantity,
        "unit": _text(unit, "unit", max_length=50),
        "unit_cost": unit_cost,
        "batch_id": str(batch_id or ""),
        "reference": (reference or "").strip(),
        "notes": (notes or "").strip(),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint("RECORD_PURCHASE", values)
    retry = _record_retry(ProductionPurchase, idempotency_key, fingerprint)
    if retry:
        return retry
    if category not in ProductionPurchase.Category.values:
        raise ValidationError({"category": "Unknown Production purchase category."})
    record = ProductionPurchase(
        purchase_date=purchase_date,
        supplier=values["supplier"],
        item_description=values["item_description"],
        category=category,
        quantity=quantity,
        unit=values["unit"],
        unit_cost=unit_cost,
        total_cost=_money_total(quantity, unit_cost),
        batch=_optional_batch(batch_id),
        reference=values["reference"],
        notes=values["notes"],
        recorded_by=actor,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    record.save(_production_service_write=True)
    return record


@transaction.atomic
def record_labour(
    *, work_date, worker, activity, effort_quantity, effort_unit, rate, batch_id,
    notes, actor, correlation_id, idempotency_key
):
    _require_permission(actor, "production.record_labour")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    effort_quantity = _decimal(
        effort_quantity, "effort_quantity", EFFORT_QUANTUM, positive=True
    )
    rate = _decimal(rate, "rate", MONEY_QUANTUM, non_negative=True)
    values = {
        "work_date": work_date,
        "worker": _text(worker, "worker", max_length=200),
        "activity": _text(activity, "activity", max_length=250),
        "effort_quantity": effort_quantity,
        "effort_unit": effort_unit,
        "rate": rate,
        "batch_id": str(batch_id or ""),
        "notes": (notes or "").strip(),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint("RECORD_LABOUR", values)
    retry = _record_retry(ProductionLabour, idempotency_key, fingerprint)
    if retry:
        return retry
    if effort_unit not in ProductionLabour.EffortUnit.values:
        raise ValidationError({"effort_unit": "Unknown labour effort unit."})
    record = ProductionLabour(
        work_date=work_date,
        worker=values["worker"],
        activity=values["activity"],
        effort_quantity=effort_quantity,
        effort_unit=effort_unit,
        rate=rate,
        total_cost=_money_total(effort_quantity, rate),
        batch=_optional_batch(batch_id),
        notes=values["notes"],
        recorded_by=actor,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    record.save(_production_service_write=True)
    return record


@transaction.atomic
def record_activity(
    *, activity_date, activity_type, batch_id, description, coverage_quantity,
    coverage_unit, person_or_team, cost, notes, actor, correlation_id, idempotency_key
):
    _require_permission(actor, "production.record_activities")
    idempotency_key = lock_idempotency_key(idempotency_key)
    correlation_id = _uuid(correlation_id, "correlation_id")
    normalized_coverage = None
    if coverage_quantity not in (None, ""):
        normalized_coverage = _decimal(
            coverage_quantity, "coverage_quantity", QUANTITY_QUANTUM, positive=True
        )
    normalized_cost = None
    if cost not in (None, ""):
        normalized_cost = _decimal(cost, "cost", MONEY_QUANTUM, non_negative=True)
    coverage_unit = (coverage_unit or "").strip()
    if bool(normalized_coverage is not None) != bool(coverage_unit):
        raise ValidationError("Coverage quantity and coverage unit must be supplied together.")
    values = {
        "activity_date": activity_date,
        "activity_type": activity_type,
        "batch_id": str(batch_id or ""),
        "description": _text(description, "description"),
        "coverage_quantity": normalized_coverage,
        "coverage_unit": coverage_unit,
        "person_or_team": (person_or_team or "").strip(),
        "cost": normalized_cost,
        "notes": (notes or "").strip(),
        "actor": str(actor.pk),
        "correlation_id": str(correlation_id),
    }
    fingerprint = _fingerprint("RECORD_ACTIVITY", values)
    retry = _record_retry(NurseryActivity, idempotency_key, fingerprint)
    if retry:
        return retry
    if activity_type not in NurseryActivity.Type.values:
        raise ValidationError({"activity_type": "Unknown nursery activity type."})
    record = NurseryActivity(
        activity_date=activity_date,
        activity_type=activity_type,
        batch=_optional_batch(batch_id),
        description=values["description"],
        coverage_quantity=normalized_coverage,
        coverage_unit=coverage_unit,
        person_or_team=values["person_or_team"],
        cost=normalized_cost,
        notes=values["notes"],
        recorded_by=actor,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    record.save(_production_service_write=True)
    return record


def _booking_location(location_id):
    if location_id is None:
        return None
    from apps.inventory.models import InventoryLocation
    location_id = _uuid(location_id, "location_id")
    if not InventoryLocation.objects.filter(pk=location_id, is_active=True, allows_saleable_stock=True).exists():
        raise ValidationError({"location_id": "Select an active saleable Location."})
    return location_id
