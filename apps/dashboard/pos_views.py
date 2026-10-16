import uuid
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.customers.models import Customer
from apps.inventory.availability import AvailabilityUnavailable, get_ready_availability
from apps.inventory.models import InventoryLocation
from apps.orders.models import Order, OrderLine
from apps.orders.services import OrderLineInput, _require_pos_permission, quote_order_lines, validate_pos_lines
from apps.orders.bookings import cancel_production_booking
from apps.orders.lifecycle import start_order_processing
from apps.payments.pos import checkout_pos, confirm_pos_payment
from apps.production.capacity import bookable_units, validate_booking_lines
from apps.production.models import ProductionBatch
from apps.products.models import ProductSaleUnit


def locations():
    return InventoryLocation.objects.filter(is_active=True, allows_saleable_stock=True).order_by("name", "pk")


def can_view_customers(user):
    return user.has_perm("customers.view") or user.has_perm("customers.view_customer")


def selected_location(raw):
    try:
        return locations().get(pk=forms.UUIDField().clean(raw))
    except (ValidationError, InventoryLocation.DoesNotExist) as error:
        raise ValidationError("Select a valid Location / Branch.") from error


def activity(request):
    value = request.POST.get("activity", request.GET.get("activity", "sales"))
    if value not in ("sales", "bookings"):
        raise Http404("Select Sales or Bookings.")
    return value


def session_key(mode):
    return "pos_cart" if mode == "sales" else "pos_booking_cart"


def pos_url(mode):
    return reverse("dashboard:pos") + ("?activity=bookings" if mode == "bookings" else "")


def cart_lines(cart, mode="sales"):
    return [OrderLineInput(product_id=uuid.UUID(v["product"]), sale_unit_id=uuid.UUID(v.get("unit", k)),
                           quantity=v["quantity"], supply_mode="READY" if mode == "sales" else "PRE_ORDER",
                           production_batch_id=uuid.UUID(v["batch"]) if mode == "bookings" else None)
            for k, v in cart.items()]


def state(request, mode="sales"):
    saved = request.session.get(session_key(mode))
    if saved is None:
        bomet = list(locations().filter(name__iexact="Bomet")[:2])
        saved = {"location": str(bomet[0].pk) if len(bomet) == 1 else "", "lines": {},
                 "key": str(uuid.uuid4()), "customer": ""}
    return saved


def validate_cart(saved, mode, location_id):
    lines = cart_lines(saved["lines"], mode)
    if mode == "bookings":
        return validate_booking_lines(lines=lines, location_id=location_id)
    return validate_pos_lines(lines=lines, location_id=location_id)


def error_message(request, error):
    messages.error(request, "; ".join(error.messages))


@login_required(login_url="accounts:login")
def pos(request):
    _require_pos_permission(request.user)
    mode = activity(request)
    saved = state(request, mode)
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "new":
                saved["lines"] = {}
                saved["customer"] = ""
            elif action == "location":
                location = selected_location(request.POST.get("location_id"))
                saved["location"] = str(location.pk)
            elif action == "remove":
                saved["lines"].pop(request.POST.get("cart_key", request.POST.get("sale_unit_id")), None)
            elif action in ("add", "update"):
                location = selected_location(request.POST.get("location_id"))
                if str(location.pk) != saved["location"]:
                    raise ValidationError("Location changed. Reload the cart before adding stock.")
                unit_id = forms.UUIDField().clean(request.POST.get("sale_unit_id"))
                unit = ProductSaleUnit.objects.select_related("product").get(
                    pk=unit_id, is_active=True, product__is_active=True, product__is_published=True)
                quantity = forms.IntegerField(min_value=1, max_value=9223372036854775807).clean(request.POST.get("quantity"))
                batch_id = forms.UUIDField().clean(request.POST.get("batch_id")) if mode == "bookings" else None
                row_key = f"{batch_id}:{unit.pk}" if batch_id else str(unit.pk)
                if action == "add":
                    quantity += saved["lines"].get(row_key, {}).get("quantity", 0)
                line = OrderLineInput(unit.product_id, unit.pk, quantity, "PRE_ORDER" if batch_id else "READY", batch_id)
                quote_order_lines(lines=[line], channel="POS")
                candidate = dict(saved["lines"])
                candidate[row_key] = {"product": str(unit.product_id), "unit": str(unit.pk), "quantity": quantity,
                                      "batch": str(batch_id) if batch_id else ""}
                validate_cart({"lines": candidate}, mode, location.pk)
                saved["lines"] = candidate
            else:
                raise ValidationError("Unknown cart action.")
            saved["key"] = str(uuid.uuid4())
        except (ValidationError, AvailabilityUnavailable) as error:
            error_message(request, error) if isinstance(error, ValidationError) else messages.error(request, str(error))
        except ProductSaleUnit.DoesNotExist:
            messages.error(request, "Product is unavailable.")
        request.session[session_key(mode)] = saved
        return redirect(pos_url(mode))
    request.session[session_key(mode)] = saved
    location = None
    try:
        location = selected_location(saved["location"])
    except ValidationError:
        pass
    search = request.GET.get("q", "").strip()
    units = ProductSaleUnit.objects.filter(is_active=True, product__is_active=True, product__is_published=True).select_related("product").prefetch_related("product__images")
    if search:
        units = units.filter(Q(product__name__icontains=search) | Q(product__sku__icontains=search))
    products = []
    if location:
        for unit in units.order_by("product__name", "name"):
            try:
                resolved, _ = quote_order_lines(lines=[OrderLineInput(unit.product_id, unit.pk, 1, "READY")], channel="POS")
            except ValidationError:
                continue
            if mode == "bookings":
                for batch in ProductionBatch.objects.filter(product=unit.product, location=location, status="IN_PRODUCTION").order_by("expected_ready_date", "pk"):
                    available = bookable_units(batch=batch, unit=unit, location_id=location.pk)
                    if available:
                        products.append({"unit": unit, "price": resolved[0][3].amount, "available": available, "batch": batch})
            else:
                availability_error = False
                try:
                    available = get_ready_availability(product=unit.product, sale_unit=unit, location_id=location.pk).available_sale_units
                except AvailabilityUnavailable:
                    available, availability_error = 0, True
                products.append({"unit": unit, "price": resolved[0][3].amount, "available": available, "availability_error": availability_error})
    cart, total = [], Decimal("0.00")
    cart_valid = False
    if saved["lines"]:
        try:
            resolved, total = quote_order_lines(lines=cart_lines(saved["lines"], mode), channel="POS")
            cart = [{"line": line, "product": product, "unit": unit, "price": price.amount, "total": subtotal,
                     "cart_key": f"{line.production_batch_id}:{unit.pk}" if line.production_batch_id else str(unit.pk)}
                    for line, product, unit, price, subtotal in resolved]
            validate_cart(saved, mode, location.pk if location else None)
            cart_valid = True
        except ValidationError as error:
            error_message(request, error)
    customers = Customer.objects.filter(is_active=True) if can_view_customers(request.user) else Customer.objects.none()
    return render(request, "dashboard/pos/checkout_live.html", {
        "locations": locations(), "location": location, "products": products, "cart": cart,
        "activity": mode, "is_booking": mode == "bookings", "total": total, "search": search, "state": saved, "customers": customers, "cart_valid": cart_valid,
    })


@login_required(login_url="accounts:login")
@require_POST
def process_sale(request):
    _require_pos_permission(request.user)
    mode = activity(request)
    saved = state(request, mode)
    try:
        # Never substitute Bomet on POST: missing/tampered input fails in DEBUG and production.
        location = selected_location(request.POST.get("location_id"))
        key = forms.UUIDField().clean(request.POST.get("idempotency_key"))
        if str(key) != saved["key"] or str(location.pk) != saved["location"]:
            raise ValidationError("The cart changed. Review it before confirming payment.")
        customer = None
        raw_customer = request.POST.get("customer", "")
        if raw_customer:
            if not can_view_customers(request.user):
                raise PermissionDenied
            customer = get_object_or_404(Customer, pk=forms.UUIDField().clean(raw_customer), is_active=True)
        order = checkout_pos(
            lines=cart_lines(saved["lines"], mode), customer=customer, actor=request.user,
            idempotency_key=key, location_id=location.pk, activity=mode,
            method=request.POST.get("payment_method"), reference=request.POST.get("reference"),
        )
    except ValidationError as error:
        error_message(request, error)
        return redirect(pos_url(mode))
    except DatabaseError:
        messages.error(request, "Payment could not be completed. Your cart is retained; please retry.")
        return redirect(pos_url(mode))
    # Sales payment and inventory issues have committed before resetting the cart.
    request.session[session_key(mode)] = {"location": saved["location"], "lines": {}, "customer": "", "key": str(uuid.uuid4())}
    outcome = "Payment Confirmed. Booking Complete." if mode == "bookings" else "Sale completed successfully."
    messages.success(request, format_html('{} <a href="{}">View {}</a>', outcome,
                                         reverse("dashboard:pos_order_detail", args=(order.pk,)), order.order_number))
    return redirect(pos_url(mode))



@login_required(login_url="accounts:login")
def order_detail(request, order_id):
    _require_pos_permission(request.user)
    order = get_object_or_404(Order.objects.select_related("location", "payment", "customer"), pk=order_id, channel="POS")
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "confirm":
                confirm_pos_payment(order_id=order.pk, method=order.payment.method,
                                    reference=request.POST.get("reference"), actor=request.user,
                                    idempotency_key=uuid.uuid5(order.creation_idempotency_key, "payment"))
                for mode in ("sales", "bookings"):
                    saved = state(request, mode)
                    if saved["key"] == str(order.creation_idempotency_key):
                        request.session[session_key(mode)] = {"location": saved["location"], "lines": {}, "customer": "", "key": str(uuid.uuid4())}
                messages.success(request, "Payment Confirmed.")
            elif action == "process":
                start_order_processing(order_id=order.pk, actor=request.user, reason="POS staff started processing",
                                       correlation_id=request.POST.get("correlation_id"), idempotency_key=request.POST.get("idempotency_key"))
            elif action == "cancel_booking":
                cancel_production_booking(order_id=order.pk, actor=request.user, reason=request.POST.get("reason"),
                                          correlation_id=request.POST.get("correlation_id"), idempotency_key=request.POST.get("idempotency_key"))
            else:
                raise ValidationError("Unknown action.")
        except ValidationError as error:
            error_message(request, error)
        except DatabaseError:
            messages.error(request, "The action could not be completed. Please retry.")
        return redirect("dashboard:pos_order_detail", order.pk)
    return render(request, "dashboard/pos/order_live.html", {
        "order": order, "is_booking": order.lines.filter(supply_mode="PRE_ORDER").exists(),
        "key": uuid.uuid4(), "correlation": uuid.uuid4(),
    })
