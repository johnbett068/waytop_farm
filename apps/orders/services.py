import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.idempotency import lock_idempotency_key
from apps.customers.models import Customer
from apps.customers.normalization import normalize_email, normalize_kenyan_phone
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .models import (
    Order,
    OrderAddressSnapshot,
    OrderContactSnapshot,
    OrderLine,
    OrderStatusEvent,
    generate_order_number,
)


MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class ContactInput:
    name: str = ""
    phone: str = ""
    email: str = ""


@dataclass(frozen=True)
class AddressInput:
    county: str
    town_or_area: str
    address_line: str
    delivery_instructions: str = ""

    @classmethod
    def from_customer_address(cls, address):
        return cls(
            county=address.county,
            town_or_area=address.town_or_area,
            address_line=address.address_line,
            delivery_instructions=address.delivery_instructions,
        )


@dataclass(frozen=True)
class OrderLineInput:
    product_id: uuid.UUID
    sale_unit_id: uuid.UUID
    quantity: int
    supply_mode: str
    production_batch_id: uuid.UUID | None = None


def _require_pos_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("pos.process_sale")
    ):
        raise PermissionDenied("POS Order creation requires pos.process_sale.")


def _normalize_contact(contact):
    contact = contact or ContactInput()
    name = contact.name.strip()
    phone = normalize_kenyan_phone(contact.phone)
    email = normalize_email(contact.email)
    if email:
        validate_email(email)
    return ContactInput(name=name, phone=phone, email=email)


def _normalize_address(address):
    if address is None:
        return None
    normalized = AddressInput(
        county=address.county.strip(),
        town_or_area=address.town_or_area.strip(),
        address_line=address.address_line.strip(),
        delivery_instructions=address.delivery_instructions.strip(),
    )
    if not normalized.county or not normalized.town_or_area or not normalized.address_line:
        raise ValidationError("Home delivery requires county, town/area, and address line.")
    return normalized


def _normalize_lines(lines):
    lines = tuple(lines)
    if not lines:
        raise ValidationError("An Order requires at least one line.")
    normalized = []
    for line in lines:
        if isinstance(line.quantity, bool) or not isinstance(line.quantity, int) or line.quantity <= 0:
            raise ValidationError("Order Line quantity must be a positive whole Sale Unit count.")
        if line.supply_mode not in OrderLine.SupplyMode.values:
            raise ValidationError("Order Line supply mode must be READY or PRE_ORDER.")
        normalized.append(
            OrderLineInput(
                product_id=uuid.UUID(str(line.product_id)),
                sale_unit_id=uuid.UUID(str(line.sale_unit_id)),
                quantity=line.quantity,
                supply_mode=line.supply_mode,
                production_batch_id=uuid.UUID(str(line.production_batch_id)) if line.production_batch_id else None,
            )
        )
    return tuple(normalized)


def _validate_channel_rules(channel, fulfillment_method, lines, contact, address, required_date):
    if channel not in Order.Channel.values:
        raise ValidationError("Order channel must be ECOMMERCE or POS.")
    if fulfillment_method not in Order.FulfillmentMethod.values:
        raise ValidationError("Fulfillment method is invalid.")

    has_preorder = any(line.supply_mode == OrderLine.SupplyMode.PRE_ORDER for line in lines)
    requires_contact = (
        channel == Order.Channel.ECOMMERCE
        or fulfillment_method == Order.FulfillmentMethod.HOME_DELIVERY
        or (has_preorder and channel != Order.Channel.POS)
    )
    if requires_contact and (not contact.name or not contact.phone):
        raise ValidationError("This Order requires a customer name and Kenyan phone number.")
    if has_preorder and required_date is None:
        raise ValidationError("A required date is mandatory when any Order Line is PRE_ORDER.")
    if fulfillment_method == Order.FulfillmentMethod.HOME_DELIVERY and address is None:
        raise ValidationError("Home delivery requires an address snapshot.")
    if fulfillment_method == Order.FulfillmentMethod.CUSTOMER_COLLECTION and address is not None:
        raise ValidationError("Customer collection must not contain a delivery address snapshot.")


def _request_matches(existing, *, customer, channel, fulfillment_method, required_date, contact, address, lines):
    if (
        existing.customer_id != (customer.pk if customer else None)
        or existing.channel != channel
        or existing.fulfillment_method != fulfillment_method
        or existing.required_date != required_date
    ):
        return False

    snapshot = existing.contact_snapshot
    if customer is None and (snapshot.name, snapshot.phone, snapshot.email) != (
        contact.name,
        contact.phone,
        contact.email,
    ):
        return False

    existing_address = getattr(existing, "address_snapshot", None)
    if address is None:
        if existing_address is not None:
            return False
    elif existing_address is None or (
        existing_address.county,
        existing_address.town_or_area,
        existing_address.address_line,
        existing_address.delivery_instructions,
    ) != (
        address.county,
        address.town_or_area,
        address.address_line,
        address.delivery_instructions,
    ):
        return False

    existing_lines = tuple(
        existing.lines.order_by("line_number").values_list(
            "product_id", "sale_unit_id", "quantity", "supply_mode", "production_batch_id"
        )
    )
    requested_lines = tuple(
        (line.product_id, line.sale_unit_id, line.quantity, line.supply_mode, line.production_batch_id) for line in lines
    )
    return existing_lines == requested_lines


def _current_price(sale_unit, at):
    prices = list(
        ProductPrice.objects.filter(
            sale_unit=sale_unit,
            is_active=True,
            effective_start__lte=at,
        ).filter(Q(effective_end__isnull=True) | Q(effective_end__gt=at))[:2]
    )
    if len(prices) != 1:
        raise ValidationError("The selected Sale Unit does not have one authoritative current price.")
    if prices[0].amount <= 0:
        raise ValidationError("Zero-price Catalog entries are not orderable in V1.")
    return prices[0]


def _new_order_number():
    for _ in range(10):
        candidate = generate_order_number()
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    raise ValidationError("A unique public Order number could not be generated.")


def quote_order_lines(*, lines, channel):
    """Resolve current catalog prices and exact totals for cart and Order snapshots."""
    lines = _normalize_lines(lines)
    at = timezone.now()
    resolved_lines = []
    total = Decimal("0.00")
    for line in lines:
        try:
            product = Product.objects.get(pk=line.product_id, is_active=True)
            sale_unit = ProductSaleUnit.objects.get(
                pk=line.sale_unit_id, product=product, is_active=True
            )
        except (Product.DoesNotExist, ProductSaleUnit.DoesNotExist) as exc:
            raise ValidationError("The selected Product and Sale Unit are not orderable.") from exc
        if channel in (Order.Channel.ECOMMERCE, Order.Channel.POS) and not product.is_published:
            raise ValidationError("This sales channel can order only published Products.")
        price = _current_price(sale_unit, at)
        line_total = (Decimal(line.quantity) * price.amount).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        total += line_total
        resolved_lines.append((line, product, sale_unit, price, line_total))

    total = total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if total <= 0:
        raise ValidationError("V1 Orders must have a positive total.")

    return resolved_lines, total


def validate_pos_lines(*, lines, location_id):
    """Validate the whole READY cart against one authoritative stock scope."""
    from apps.inventory.models import InventoryItem, InventoryLocation
    from apps.inventory.availability import get_ready_availability, AvailabilityUnavailable
    if not location_id or not InventoryLocation.objects.filter(pk=location_id, is_active=True, allows_saleable_stock=True).exists():
        raise ValidationError("Select an active saleable Location / Branch.")
    normalized_lines = _normalize_lines(lines)
    required_by_product = {}
    for line in normalized_lines:
        if line.supply_mode != OrderLine.SupplyMode.READY:
            raise ValidationError("Location-targeted POS currently supports READY stock only.")
        try:
            product = Product.objects.get(pk=line.product_id, is_active=True, is_published=True)
            unit = ProductSaleUnit.objects.get(pk=line.sale_unit_id, product=product, is_active=True)
            available = get_ready_availability(product=product, sale_unit=unit, location_id=location_id)
        except (Product.DoesNotExist, ProductSaleUnit.DoesNotExist, AvailabilityUnavailable) as error:
            raise ValidationError("Product is unavailable at the selected Location.") from error
        required_by_product[product.pk] = required_by_product.get(product.pk, Decimal("0")) + unit.base_quantity * line.quantity
        if line.quantity > available.available_sale_units:
            raise ValidationError("Insufficient stock at the selected Location.")
    # Mixed Sale Units for the same Product must not oversell its shared base quantity.
    for product_id, required in required_by_product.items():
        from apps.inventory.availability import available_ready_base_quantity
        item = InventoryItem.objects.get(product_id=product_id)
        try:
            available_base, _ = available_ready_base_quantity(inventory_item=item, calculated_at=timezone.now(), location_id=location_id)
        except AvailabilityUnavailable as error:
            raise ValidationError("Product is unavailable at the selected Location.") from error
        if required > available_base:
            raise ValidationError("Combined Sale Units exceed stock at the selected Location.")


@transaction.atomic
def create_pending_order(
    *,
    channel,
    fulfillment_method,
    lines,
    creation_idempotency_key,
    contact=None,
    address=None,
    customer=None,
    required_date=None,
    actor=None,
    location_id=None,
    payment_method="MPESA",
):
    """Create one immutable PENDING Order and PENDING Payment aggregate."""
    from apps.payments.models import Payment, PaymentStatusEvent

    if payment_method not in Payment.Method.values or (channel != "POS" and payment_method != "MPESA"):
        raise ValidationError("Unsupported payment method for this channel.")
    idempotency_key = lock_idempotency_key(creation_idempotency_key)
    if channel == Order.Channel.POS:
        _require_pos_permission(actor)
        if not location_id:
            raise ValidationError({"location_id": "Select a Location / Branch."})
    if location_id is not None:
        try:
            location_id = uuid.UUID(str(location_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError({"location_id": "Select a valid Location / Branch."}) from error

    if channel == Order.Channel.POS:
        from apps.inventory.models import InventoryLocation
        if not InventoryLocation.objects.filter(pk=location_id, is_active=True, allows_saleable_stock=True).exists():
            raise ValidationError({"location_id": "Select an active saleable Location / Branch."})

    normalized_lines = _normalize_lines(lines)
    normalized_address = _normalize_address(address)

    existing = (
        Order.objects.select_for_update()
        .filter(creation_idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        if existing.payment.method != payment_method:
            raise ValidationError("Idempotency key reused for a different payment method.")
        if existing.location_id != location_id:
            raise ValidationError("The creation idempotency key was reused for a different Location.")
        if required_date is None and any(line.production_batch_id for line in normalized_lines):
            required_date = existing.required_date
        normalized_contact = (
            ContactInput(
                name=existing.contact_snapshot.name,
                phone=existing.contact_snapshot.phone,
                email=existing.contact_snapshot.email,
            )
            if customer is not None and existing.customer_id == customer.pk
            else _normalize_contact(contact)
        )
        _validate_channel_rules(
            channel,
            fulfillment_method,
            normalized_lines,
            normalized_contact,
            normalized_address,
            required_date,
        )
        if not _request_matches(
            existing,
            customer=customer,
            channel=channel,
            fulfillment_method=fulfillment_method,
            required_date=required_date,
            contact=normalized_contact,
            address=normalized_address,
            lines=normalized_lines,
        ):
            raise ValidationError("The creation idempotency key was already used for different input.")
        return existing

    batches = {}
    if any(line.production_batch_id for line in normalized_lines):
        if channel != Order.Channel.POS:
            raise ValidationError("Production bookings require the POS booking channel.")
        from apps.production.capacity import validate_booking_lines
        batches = validate_booking_lines(lines=normalized_lines, location_id=location_id, lock=True)
        if required_date is None:
            required_date = max(batch.expected_ready_date for batch in batches.values())

    if customer is not None:
        customer = Customer.objects.select_for_update().get(pk=customer.pk)
        if not customer.is_active:
            raise ValidationError("An inactive Customer cannot be attached to a new Order.")
        normalized_contact = ContactInput(
            name=customer.display_name,
            phone=customer.phone,
            email=customer.email,
        )
    else:
        normalized_contact = _normalize_contact(contact)

    _validate_channel_rules(
        channel,
        fulfillment_method,
        normalized_lines,
        normalized_contact,
        normalized_address,
        required_date,
    )

    if channel == Order.Channel.POS and not batches:
        from apps.inventory.models import InventoryItem
        # Match confirmation's per-product serialization. A pending order never reserves stock.
        list(InventoryItem.objects.select_for_update(of=("self",)).filter(
            product_id__in=[line.product_id for line in normalized_lines]).order_by("pk"))
        validate_pos_lines(lines=normalized_lines, location_id=location_id)
    resolved_lines, total = quote_order_lines(lines=normalized_lines, channel=channel)

    order = Order.objects.create(
        order_number=_new_order_number(),
        creation_idempotency_key=idempotency_key,
        customer=customer,
        channel=channel,
        location_id=location_id,
        fulfillment_method=fulfillment_method,
        required_date=required_date,
        total_amount=total,
    )
    OrderContactSnapshot.objects.create(
        order=order,
        name=normalized_contact.name,
        phone=normalized_contact.phone,
        email=normalized_contact.email,
    )
    if normalized_address is not None:
        OrderAddressSnapshot.objects.create(order=order, **normalized_address.__dict__)

    for line_number, (line, product, sale_unit, price, line_total) in enumerate(
        resolved_lines, start=1
    ):
        OrderLine.objects.create(
            order=order,
            line_number=line_number,
            product=product,
            sale_unit=sale_unit,
            source_price=price,
            product_sku=product.sku,
            product_name=product.name,
            sale_unit_name=sale_unit.name,
            base_quantity=sale_unit.base_quantity,
            quantity=line.quantity,
            unit_price=price.amount,
            line_total=line_total,
            supply_mode=line.supply_mode,
            production_batch_id=line.production_batch_id,
            expected_ready_date=batches[line.production_batch_id].expected_ready_date if line.production_batch_id else None,
        )

    correlation_id = uuid.uuid4()
    order_event = OrderStatusEvent(
        order=order,
        previous_status=None,
        new_status=Order.Status.PENDING,
        actor=actor if channel == Order.Channel.POS else None,
        reason="Order created",
        correlation_id=correlation_id,
        idempotency_key=uuid.uuid5(order.id, "order-created"),
    )
    order_event.save(_creation_service_write=True)
    payment = Payment.objects.create(order=order, amount=total, method=payment_method)
    payment_event = PaymentStatusEvent(
        payment=payment,
        previous_state=None,
        new_state=Payment.State.PENDING,
        actor=actor if channel == Order.Channel.POS else None,
        reason="Payment created",
        correlation_id=correlation_id,
        idempotency_key=uuid.uuid5(payment.id, "payment-created"),
    )
    payment_event.save(_creation_service_write=True)
    return order


# Public Phase 1G cancellation boundary; imported here for the established service API.
from .lifecycle import cancel_ready_order, start_order_processing  # noqa: E402,F401
