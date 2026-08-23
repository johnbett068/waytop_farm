import uuid
from decimal import Decimal, InvalidOperation, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key
from apps.inventory.models import InventoryItem
from apps.orders.models import OrderLine

from .models import Commitment, CommitmentEvent


BASE_QUANTITY_QUANTUM = Decimal("0.001")


def _require_permission(actor, permission):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied(f"Commitment operation requires {permission}.")


def _require_confirmation_permissions(actor):
    _require_permission(actor, "payments.verify")
    _require_permission(actor, "commitments.allocate")


def _uuid(value, field_name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError({field_name: "A valid UUID is required."}) from error


def _base_quantity(value):
    try:
        quantity = Decimal(str(value))
        quantized = quantity.quantize(BASE_QUANTITY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Commitment base quantity must be a valid Decimal(32,3).") from error
    if not quantity.is_finite() or quantity <= 0 or quantity != quantized:
        raise ValidationError("Commitment base quantity must be positive and exact to three decimals.")
    if max(quantity.adjusted() + 1, 0) > 29:
        raise ValidationError("Commitment base quantity exceeds Decimal(32,3) precision.")
    return quantized


def _matches_creation(
    commitment,
    *,
    order_line_id,
    actor,
    confirmed_at,
    correlation_id,
    reason,
    source_type,
    source_reference,
):
    event = commitment.events.get(idempotency_key=commitment.creation_idempotency_key)
    return (
        commitment.order_line_id == order_line_id
        and commitment.confirmed_at == confirmed_at
        and commitment.creation_correlation_id == correlation_id
        and event.actor_id == actor.pk
        and event.reason == reason
        and event.source_type == source_type
        and event.source_reference == source_reference
    )


def _create_commitment_for_confirmation(
    *,
    order_line_id,
    actor,
    confirmed_at,
    correlation_id,
    idempotency_key,
    reason,
    source_type,
    source_reference,
):
    """Internal write for the future atomic confirmation orchestrator only.

    The caller must own the outer transaction and the contract lock order. There
    is deliberately no public creation command or endpoint in Phase 1E-B.
    """
    if not connection.in_atomic_block:
        raise ValidationError("Commitment creation requires the outer confirmation transaction.")
    _require_confirmation_permissions(actor)
    if confirmed_at is None or not hasattr(confirmed_at, "utcoffset") or timezone.is_naive(confirmed_at):
        raise ValidationError("Confirmation time must be a server-generated aware datetime.")
    correlation_id = _uuid(correlation_id, "correlation_id")
    idempotency_key = lock_idempotency_key(idempotency_key)
    reason = (reason or "").strip()
    source_type = (source_type or "").strip()
    source_reference = (source_reference or "").strip()
    if not reason or not source_type or not source_reference:
        raise ValidationError("Commitment creation requires reason and source reference audit data.")

    existing = Commitment.objects.filter(
        creation_idempotency_key=idempotency_key
    ).first()
    normalized_line_id = _uuid(order_line_id, "order_line_id")
    if existing is not None:
        if not _matches_creation(
            existing,
            order_line_id=normalized_line_id,
            actor=actor,
            confirmed_at=confirmed_at,
            correlation_id=correlation_id,
            reason=reason,
            source_type=source_type,
            source_reference=source_reference,
        ):
            raise ValidationError("Commitment idempotency key was reused with different input.")
        return existing

    try:
        line = (
            OrderLine.objects.select_for_update()
            .select_related("order")
            .get(pk=normalized_line_id)
        )
        item = (
            InventoryItem.objects.select_for_update()
            .select_related("product")
            .get(product_id=line.product_id)
        )
    except OrderLine.DoesNotExist as error:
        raise ValidationError("Commitment creation references an unknown Order Line.") from error
    except InventoryItem.DoesNotExist as error:
        raise ValidationError(
            "Order Line Product does not have an Inventory Item."
        ) from error
    if not item.is_active or item.base_unit != item.product.base_inventory_unit:
        raise ValidationError("Order Line does not map to an active compatible Inventory Item.")

    existing = Commitment.objects.filter(
        creation_idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        if not _matches_creation(
            existing,
            order_line_id=normalized_line_id,
            actor=actor,
            confirmed_at=confirmed_at,
            correlation_id=correlation_id,
            reason=reason,
            source_type=source_type,
            source_reference=source_reference,
        ):
            raise ValidationError("Commitment idempotency key was reused with different input.")
        return existing
    if Commitment.objects.filter(order_line_id=line.pk).exists():
        raise ValidationError("This Order Line already has a Commitment.")

    base_per_unit = _base_quantity(line.base_quantity)
    with localcontext() as context:
        context.prec = 50
        committed_base = _base_quantity(Decimal(line.quantity) * base_per_unit)
    required_date = (
        line.order.required_date
        if line.supply_mode == OrderLine.SupplyMode.PRE_ORDER
        else None
    )
    commitment = Commitment(
        order=line.order,
        order_line=line,
        inventory_item=item,
        committed_quantity=line.quantity,
        base_quantity_per_sale_unit=base_per_unit,
        committed_base_quantity=committed_base,
        outstanding_quantity=line.quantity,
        outstanding_base_quantity=committed_base,
        confirmed_at=confirmed_at,
        required_date=required_date,
        creation_correlation_id=correlation_id,
        creation_idempotency_key=idempotency_key,
    )
    commitment.save(_commitment_service_write=True)
    CommitmentEvent(
        commitment=commitment,
        previous_state=None,
        new_state=Commitment.State.ACTIVE,
        commercial_quantity=line.quantity,
        base_quantity=committed_base,
        actor=actor,
        reason=reason,
        source_type=source_type,
        source_reference=source_reference,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    ).save(_commitment_service_write=True)
    return commitment


def list_fifo_commitments(*, inventory_item_id, supply_mode, actor):
    """Return an authorized internal FIFO projection; never a customer response."""
    _require_permission(actor, "commitments.view")
    if supply_mode not in OrderLine.SupplyMode.values:
        raise ValidationError("FIFO supply mode must be READY or PRE_ORDER.")
    return Commitment.objects.filter(
        inventory_item_id=_uuid(inventory_item_id, "inventory_item_id"),
        order_line__supply_mode=supply_mode,
        state=Commitment.State.ACTIVE,
    ).order_by("confirmed_at", "fifo_sequence")
