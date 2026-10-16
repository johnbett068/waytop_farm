import re
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer, CustomerAddress
from apps.payments.models import Payment, PaymentStatusEvent
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .models import Order, OrderLine, OrderStatusEvent
from .services import AddressInput, ContactInput, OrderLineInput, create_pending_order


class EmptyOrderRuntimeTests(SimpleTestCase):
    def test_order_routes_render_honest_empty_states(self):
        expectations = {
            "orders:checkout": "Checkout is not available yet",
            "orders:success": "No order confirmation is available",
            "orders:tracking": "No orders are available to track",
            "orders:history": "No order history yet",
        }
        for route, copy in expectations.items():
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-runtime-empty-state")
                self.assertContains(response, copy)

    def test_query_parameters_cannot_reenable_demo_orders(self):
        for route in ("orders:checkout", "orders:success", "orders:tracking", "orders:history"):
            response = self.client.get(reverse(route) + "?state=success")
            for fabricated in (
                "Jane Chebet", "WTF-260716-1042", "KES 6,870",
                "Anna F1 Tomato", "Payment Confirmed",
            ):
                self.assertNotContains(response, fabricated)

    def test_frontend_scripts_have_no_seeded_checkout_or_tracking_record(self):
        with open("static/js/checkout.js", encoding="utf-8") as script:
            checkout_source = script.read()
        with open("static/js/order-tracking.js", encoding="utf-8") as script:
            tracking_source = script.read()
        self.assertNotIn("'anna-f1-tomato': { quantity: 2 }", checkout_source)
        self.assertNotIn("const validOrder", tracking_source)
        self.assertNotIn("const validPhone", tracking_source)


class PendingOrderCreationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-ORD-001",
            slug="order-product",
            name="Order Product",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product, name="Tray", base_quantity=Decimal("128.000")
        )
        self.price = ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("250.50"),
            effective_start=timezone.now() - timedelta(hours=1),
        )

    def line(self, *, quantity=2, supply_mode=OrderLine.SupplyMode.READY, **overrides):
        values = {
            "product_id": self.product.id,
            "sale_unit_id": self.sale_unit.id,
            "quantity": quantity,
            "supply_mode": supply_mode,
        }
        values.update(overrides)
        return OrderLineInput(**values)

    def create_ecommerce(self, **overrides):
        values = {
            "channel": Order.Channel.ECOMMERCE,
            "fulfillment_method": Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            "lines": [self.line()],
            "creation_idempotency_key": uuid.uuid4(),
            "contact": ContactInput(
                name="  Jane Buyer  ", phone="0724 853 914", email=" Jane@Example.COM "
            ),
        }
        values.update(overrides)
        return create_pending_order(**values)

    def test_initial_order_and_payment_events_are_service_only_and_unique(self):
        order = self.create_ecommerce()
        order_event = OrderStatusEvent(
            order=order,
            previous_status=None,
            new_status=Order.Status.PENDING,
            reason="Bypass attempt",
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )
        payment_event = PaymentStatusEvent(
            payment=order.payment,
            previous_state=None,
            new_state=Payment.State.PENDING,
            reason="Bypass attempt",
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            order_event.save()
        with self.assertRaises(ValidationError):
            payment_event.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Model.save(order_event)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Model.save(payment_event)

        self.assertEqual(order.status_events.count(), 1)
        self.assertEqual(order.payment.status_events.count(), 1)

    def test_ecommerce_creation_persists_complete_pending_aggregate(self):
        order = self.create_ecommerce()
        line = order.lines.get()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total_amount, Decimal("501.00"))
        self.assertRegex(order.order_number, r"^WTF-[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){2}$")
        self.assertIsNone(order.customer)
        self.assertEqual(
            (order.contact_snapshot.name, order.contact_snapshot.phone, order.contact_snapshot.email),
            ("Jane Buyer", "+254724853914", "jane@example.com"),
        )
        self.assertEqual(line.product_sku, self.product.sku)
        self.assertEqual(line.product_name, self.product.name)
        self.assertEqual(line.sale_unit_name, "Tray")
        self.assertEqual(line.base_quantity, Decimal("128.000"))
        self.assertEqual(line.unit_price, Decimal("250.50"))
        self.assertEqual(line.line_total, Decimal("501.00"))
        self.assertEqual(line.confirmed_quantity, 0)
        self.assertEqual(line.outstanding_quantity, 0)
        self.assertEqual(order.payment.state, Payment.State.PENDING)
        self.assertEqual(order.payment.amount, order.total_amount)
        self.assertEqual(order.status_events.get().new_status, Order.Status.PENDING)
        self.assertEqual(order.payment.status_events.get().new_state, Payment.State.PENDING)

    def test_pos_requires_native_permission_and_explicit_location(self):
        actor = get_user_model().objects.create_user(
            username="cashier", password="safe-password", is_staff=True
        )
        values = {
            "channel": Order.Channel.POS,
            "fulfillment_method": Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            "lines": [self.line()],
            "creation_idempotency_key": uuid.uuid4(),
            "actor": actor,
        }
        with self.assertRaises(PermissionDenied):
            create_pending_order(**values)
        actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="pos", codename="process_sale")
        )
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            actor.__dict__.pop(cache_name, None)
        with self.assertRaisesMessage(ValidationError, "Select a Location / Branch"):
            create_pending_order(**values)

    def test_customer_link_is_explicit_protected_and_snapshotted(self):
        customer = Customer.objects.create(
            display_name="Original Name", phone="0724 853 914", email="Original@Example.com"
        )
        order = self.create_ecommerce(customer=customer, contact=None)
        customer.display_name = "Changed Name"
        customer.phone = "0712 345 678"
        customer.save()
        order.contact_snapshot.refresh_from_db()
        self.assertEqual(order.contact_snapshot.name, "Original Name")
        self.assertEqual(order.contact_snapshot.phone, "+254724853914")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.filter(pk=customer.pk).delete()

    def test_inactive_customer_is_rejected_without_automatic_matching(self):
        inactive = Customer.objects.create(display_name="Inactive", is_active=False)
        with self.assertRaises(ValidationError):
            self.create_ecommerce(customer=inactive)
        matching = Customer.objects.create(display_name="Matching", phone="0724 853 914")
        guest_order = self.create_ecommerce(creation_idempotency_key=uuid.uuid4())
        self.assertIsNone(guest_order.customer)
        self.assertNotEqual(guest_order.contact_snapshot.name, matching.display_name)

    def test_home_delivery_copies_address_without_customer_address_relationship(self):
        customer = Customer.objects.create(display_name="Delivery Buyer", phone="0724 853 914")
        current = CustomerAddress.objects.create(
            customer=customer,
            label="Home",
            county="Bomet",
            town_or_area="Sotik",
            address_line="Near the market",
            delivery_instructions="Call first",
        )
        order = self.create_ecommerce(
            customer=customer,
            fulfillment_method=Order.FulfillmentMethod.HOME_DELIVERY,
            address=AddressInput.from_customer_address(current),
        )
        current.address_line = "Changed later"
        current.save()
        order.address_snapshot.refresh_from_db()
        self.assertEqual(order.address_snapshot.address_line, "Near the market")
        self.assertFalse(hasattr(order.address_snapshot, "label"))
        self.assertFalse(hasattr(order.address_snapshot, "customer_address"))

    def test_address_presence_matches_fulfillment_method(self):
        address = AddressInput("Bomet", "Sotik", "Near the market")
        with self.assertRaises(ValidationError):
            self.create_ecommerce(
                fulfillment_method=Order.FulfillmentMethod.HOME_DELIVERY, address=None
            )
        with self.assertRaises(ValidationError):
            self.create_ecommerce(address=address)

    def test_preorder_and_mixed_order_require_date_and_remain_unconfirmed(self):
        preorder = self.line(quantity=3, supply_mode=OrderLine.SupplyMode.PRE_ORDER)
        with self.assertRaises(ValidationError):
            self.create_ecommerce(lines=[preorder])
        order = self.create_ecommerce(
            lines=[self.line(), preorder], required_date=timezone.localdate() + timedelta(days=30)
        )
        self.assertEqual(
            list(order.lines.values_list("supply_mode", flat=True)),
            [OrderLine.SupplyMode.READY, OrderLine.SupplyMode.PRE_ORDER],
        )
        self.assertTrue(all(line.confirmed_quantity == 0 for line in order.lines.all()))

    def test_contact_and_integer_quantity_rules_are_enforced(self):
        with self.assertRaises(ValidationError):
            self.create_ecommerce(contact=ContactInput(name="Jane", phone=""))
        for quantity in (0, -1, Decimal("1.5"), True):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.create_ecommerce(
                    lines=[self.line(quantity=quantity)], creation_idempotency_key=uuid.uuid4()
                )

    def test_catalog_chain_publication_and_current_price_are_enforced(self):
        other = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-ORD-002", slug="other", name="Other", base_inventory_unit="seedling"
        )
        with self.assertRaises(ValidationError):
            self.create_ecommerce(
                lines=[self.line(product_id=other.id)], creation_idempotency_key=uuid.uuid4()
            )
        self.product.is_published = False
        self.product.save()
        with self.assertRaises(ValidationError):
            self.create_ecommerce(creation_idempotency_key=uuid.uuid4())

    def test_price_and_names_remain_historical_after_catalog_changes(self):
        order = self.create_ecommerce()
        original_line = order.lines.get()
        self.price.effective_end = timezone.now()
        self.price.save()
        ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("999.00"),
            effective_start=self.price.effective_end,
        )
        self.product.name = "Renamed Product"
        self.product.save()
        original_line.refresh_from_db()
        self.assertEqual(original_line.product_name, "Order Product")
        self.assertEqual(original_line.unit_price, Decimal("250.50"))
        self.assertEqual(original_line.line_total, Decimal("501.00"))

    def test_creation_is_idempotent_and_rejects_key_reuse_with_different_input(self):
        key = uuid.uuid4()
        first = self.create_ecommerce(creation_idempotency_key=key)
        second = self.create_ecommerce(creation_idempotency_key=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderLine.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.create_ecommerce(
                creation_idempotency_key=key,
                lines=[self.line(quantity=3)],
            )

    def test_idempotent_retry_returns_existing_order_after_customer_deactivation(self):
        customer = Customer.objects.create(display_name="Later inactive", phone="0724 853 914")
        key = uuid.uuid4()
        order = self.create_ecommerce(customer=customer, contact=None, creation_idempotency_key=key)
        customer.is_active = False
        customer.save()
        retried = self.create_ecommerce(
            customer=customer, contact=None, creation_idempotency_key=key
        )
        self.assertEqual(retried.pk, order.pk)

    def test_pending_commercial_records_and_future_transitions_are_blocked(self):
        order = self.create_ecommerce()
        order.status = Order.Status.CONFIRMED
        with self.assertRaises(ValidationError):
            order.save()
        line = order.lines.get()
        line.confirmed_quantity = line.quantity
        with self.assertRaises(ValidationError):
            line.save()
        with self.assertRaises(ValidationError):
            OrderStatusEvent.objects.create(
                order=order,
                previous_status=Order.Status.PENDING,
                new_status=Order.Status.CONFIRMED,
                idempotency_key=uuid.uuid4(),
            )
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.PENDING)

    def test_order_location_reuses_inventory_without_duplicate_domain_fields(self):
        fields = {field.name for field in Order._meta.get_fields()}
        self.assertTrue(
            {"branch", "inventory", "availability", "commitment", "production"}.isdisjoint(fields)
        )

    def test_ratified_native_permissions_exist(self):
        for app_label, codename in (
            ("orders", "view"),
            ("orders", "cancel"),
            ("orders", "process"),
            ("pos", "process_sale"),
        ):
            self.assertTrue(
                Permission.objects.filter(
                    content_type__app_label=app_label, codename=codename
                ).exists()
            )
