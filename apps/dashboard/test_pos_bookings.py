import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.commitments.models import Commitment
from apps.inventory.models import InventoryMovement, Reservation, SourceAllocation, StockPosition
from apps.orders.bookings import cancel_production_booking
from apps.orders.lifecycle import start_order_processing
from apps.orders.models import Order, OrderLine
from apps.orders.services import OrderLineInput, create_pending_order
from apps.payments.models import Payment, PaymentEvidence, PaymentVerificationAttempt
from apps.payments.pos import checkout_pos
from apps.production.capacity import bookable_units, remaining_capacity
from apps.production.models import ProductionBatch
from apps.production.services import create_batch, update_batch, transition_batch
from apps.products.models import ProductPrice, ProductSaleUnit
from . import test_pos as location_fixtures


class POSBookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        location_fixtures.POSLocationTests.setUpTestData.__func__(cls)
        cls.batch = cls.make_batch(cls.bomet, "BOMET-PRODUCTION", "3500")
        cls.nairobi_batch = cls.make_batch(cls.other, "OTHER-PRODUCTION", "1500")
        cls.tray = ProductSaleUnit.objects.create(product=cls.product, name="Tray", base_quantity=Decimal("150.000"))
        ProductPrice.objects.create(sale_unit=cls.tray, amount=Decimal("1500.25"), effective_start=timezone.now()-timedelta(days=1))

    @classmethod
    def make_batch(cls, location, number, quantity):
        batch = create_batch(batch_number=number, product_id=cls.product.pk, location_id=location.pk if location else None,
                             start_date=timezone.localdate(), expected_ready_date=timezone.localdate()+timedelta(days=15),
                             quantity_started=quantity, notes="", actor=cls.actor,
                             correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
        return transition_batch(batch_id=batch.pk, to_status="IN_PRODUCTION", reason="Production started",
                                actor=cls.actor, correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())

    def setUp(self):
        self.client.force_login(self.actor)

    def line(self, quantity=1, batch=None, unit=None):
        batch, unit = batch or self.batch, unit or self.unit
        return OrderLineInput(self.product.pk, unit.pk, quantity, "PRE_ORDER", batch.pk)

    def checkout(self, **changes):
        args = dict(lines=[self.line()], location_id=self.bomet.pk, customer=None, method="CASH", reference="",
                    actor=self.actor, idempotency_key=uuid.uuid4(), activity="bookings")
        args.update(changes)
        return checkout_pos(**args)

    def decrease(self, quantity):
        return update_batch(batch_id=self.batch.pk, current_quantity=quantity,
                            expected_ready_date=self.batch.expected_ready_date, notes="", reason="Audited production loss",
                            actor=self.actor, correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())

    def add(self, mode="bookings", quantity=2):
        self.client.get(reverse("dashboard:pos"), {"activity": mode})
        return self.client.post(reverse("dashboard:pos"), {
            "activity": mode, "action": "add", "location_id": self.bomet.pk, "quantity": quantity,
            "sale_unit_id": self.unit.pk, "batch_id": self.batch.pk if mode == "bookings" else "",
        }, follow=True)

    def payload(self, mode="bookings", method="CASH"):
        cart = self.client.session["pos_booking_cart" if mode == "bookings" else "pos_cart"]
        return dict(activity=mode, location_id=cart["location"], idempotency_key=cart["key"],
                    payment_method=method, reference="BOOKING-MPESA" if method == "MPESA" else "", customer="")

    def test_cash_booking_confirms_without_current_inventory_or_mpesa(self):
        before = list(StockPosition.objects.values_list("pk", "on_hand_base_quantity"))
        with patch("apps.payments.pos.submit_payment_evidence", side_effect=AssertionError("Cash must not invoke M-Pesa")):
            order = self.checkout(lines=[self.line(3500)])
        self.assertEqual((order.status, order.payment.state, order.payment.method), ("CONFIRMED", "CONFIRMED", "CASH"))
        self.assertIsNone(order.customer)
        self.assertIsNone(order.payment.provider_reference)
        self.assertEqual(order.lines.get().production_batch_id, self.batch.pk)
        self.assertEqual(order.location_id, self.bomet.pk)
        self.assertEqual(Commitment.objects.get().outstanding_base_quantity, Decimal("3500.000"))
        self.assertFalse(PaymentEvidence.objects.exists())
        self.assertFalse(PaymentVerificationAttempt.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(SourceAllocation.objects.exists())
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(list(StockPosition.objects.values_list("pk", "on_hand_base_quantity")), before)
        with self.assertRaises(ValidationError):
            start_order_processing(order_id=order.pk, actor=self.actor, reason="Cannot process future supply",
                                   correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())

    def test_mpesa_booking_is_confirmed_once_and_audited(self):
        key = uuid.uuid4()
        first = self.checkout(method="MPESA", reference=" reference-001 ", idempotency_key=key)
        second = self.checkout(method="MPESA", reference="REFERENCE-001", idempotency_key=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.payment.provider_reference, "REFERENCE-001")
        for model in (Order, Payment, Commitment, PaymentEvidence, PaymentVerificationAttempt):
            self.assertEqual(model.objects.count(), 1)
        self.assertEqual(first.payment.state, "CONFIRMED")
        with self.assertRaises(ValidationError):
            self.checkout(method="MPESA", reference="REFERENCE-001")

    def test_reference_required_and_invalid_payment_has_no_side_effects(self):
        for method, reference in (("MPESA", ""), ("MPESA", " " * 2), ("MPESA", "X"*65), ("CARD", ""), ("CASH", "MPESA-REF")):
            with self.subTest(method=method, reference=reference), self.assertRaises(ValidationError):
                self.checkout(method=method, reference=reference)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Commitment.objects.exists())

    def test_changed_idempotent_payload_is_rejected(self):
        key = uuid.uuid4()
        self.checkout(idempotency_key=key)
        for changes in (dict(lines=[self.line(2)]), dict(location_id=self.other.pk),
                        dict(lines=[self.line(batch=self.nairobi_batch)]), dict(method="MPESA", reference="DIFFERENT"),
                        dict(activity="sales")):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.checkout(idempotency_key=key, **changes)
        self.assertEqual(Order.objects.count(), 1)

    def test_current_quantity_including_initial_value_is_capacity(self):
        self.assertEqual(remaining_capacity(self.batch), Decimal("3500.000"))
        self.checkout(lines=[self.line(1500)])
        self.assertEqual(remaining_capacity(self.batch), Decimal("2000.000"))
        batch = self.decrease("3200.000")
        self.assertEqual(remaining_capacity(batch), Decimal("1700.000"))
        self.assertEqual(batch.history.filter(operation="UPDATED").get().previous_quantity, Decimal("3500.000"))
        with self.assertRaises(ValidationError):
            self.decrease("3400.000")

    def test_exact_limit_succeeds_excess_rejected_and_no_rounding_up(self):
        self.assertEqual(bookable_units(batch=self.batch, unit=self.tray, location_id=self.bomet.pk), 23)
        with self.assertRaises(ValidationError):
            self.checkout(lines=[self.line(24, unit=self.tray)])
        self.checkout(lines=[self.line(23, unit=self.tray)])
        self.assertEqual(remaining_capacity(self.batch), Decimal("50.000"))
        self.checkout(lines=[self.line(50)])
        self.assertEqual(remaining_capacity(self.batch), Decimal("0.000"))
        with self.assertRaises(ValidationError):
            self.checkout()

    def test_mixed_sale_units_share_one_capacity(self):
        with self.assertRaises(ValidationError):
            self.checkout(lines=[self.line(23, unit=self.tray), self.line(51)])
        self.assertFalse(Order.objects.exists())

    def test_decimal_capacity_is_exact(self):
        unit = ProductSaleUnit.objects.create(product=self.product, name="Decimal unit", base_quantity=Decimal("0.125"))
        ProductPrice.objects.create(sale_unit=unit, amount=Decimal("0.15"), effective_start=timezone.now()-timedelta(days=1))
        self.decrease("1.001")
        self.checkout(lines=[self.line(8, unit=unit)])
        self.batch.refresh_from_db()
        self.assertEqual(remaining_capacity(self.batch), Decimal("0.001"))
        self.assertEqual(Payment.objects.get().amount, Decimal("1.20"))

    def test_cancelled_booking_releases_capacity_without_stock_or_payment_change(self):
        order = self.checkout(lines=[self.line(1000)])
        args = dict(order_id=order.pk, actor=self.actor, reason="Customer cancelled", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
        cancel_production_booking(**args)
        cancel_production_booking(**args)
        self.assertEqual(remaining_capacity(self.batch), Decimal("3500.000"))
        self.assertEqual(Commitment.objects.get().state, "CANCELLED")
        self.assertEqual(Payment.objects.get().state, "CONFIRMED")
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertFalse(Reservation.objects.exists())

    def test_locations_are_isolated_in_both_directions(self):
        for batch, location in ((self.batch, self.other), (self.nairobi_batch, self.bomet)):
            with self.assertRaises(ValidationError):
                self.checkout(lines=[self.line(batch=batch)], location_id=location.pk)
        self.checkout(lines=[self.line(1000)])
        self.assertEqual(remaining_capacity(self.nairobi_batch), Decimal("1500.000"))
        self.checkout(lines=[self.line(1500, batch=self.nairobi_batch)], location_id=self.other.pk)
        self.assertEqual(remaining_capacity(self.batch), Decimal("2500.000"))

    def test_unassigned_missing_readiness_zero_or_nonproduction_not_bookable(self):
        # Pure projection tests do not fabricate invalid persisted records.
        for field, value in (("expected_ready_date", None), ("current_quantity", Decimal("0")),
                             ("status", "PLANNED"), ("status", "READY"), ("status", "CLOSED"), ("location_id", None)):
            batch = ProductionBatch.objects.get(pk=self.batch.pk)
            setattr(batch, field, value)
            self.assertEqual(bookable_units(batch=batch, unit=self.unit, location_id=self.bomet.pk), 0)
        batch = self.make_batch(None, "UNASSIGNED", "500")
        with self.assertRaises(ValidationError):
            self.checkout(lines=[self.line(batch=batch)])

    def test_losses_below_active_bookings_block_further_booking(self):
        self.checkout(lines=[self.line(2000)])
        batch = self.decrease("1500")
        self.assertEqual(remaining_capacity(batch), Decimal("0.000"))
        with self.assertRaises(ValidationError):
            self.checkout()
        self.assertEqual(Commitment.objects.get().outstanding_quantity, 2000)

    def test_readiness_and_batch_location_snapshots_retained(self):
        order = self.checkout()
        line = order.lines.get()
        self.assertEqual(line.expected_ready_date, self.batch.expected_ready_date)
        self.assertEqual(order.required_date, self.batch.expected_ready_date)
        with self.assertRaises(ValidationError):
            update_batch(batch_id=self.batch.pk, current_quantity=self.batch.current_quantity,
                         expected_ready_date=self.batch.expected_ready_date, notes="", reason="Move batch",
                         location_id=self.other.pk, actor=self.actor, correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())

    def test_separate_tabs_carts_and_readiness_display(self):
        self.add("sales")
        sales = self.client.session["pos_cart"]
        response = self.add()
        self.assertContains(response, "Bookings")
        self.assertContains(response, "Expected readiness")
        self.assertContains(response, "In Production")
        self.assertNotContains(response, "Verify payment")
        self.assertEqual(self.client.session["pos_cart"], sales)
        self.assertTrue(self.client.session["pos_booking_cart"]["lines"])

    def test_both_methods_clear_both_carts_only_after_confirmation(self):
        for mode in ("sales", "bookings"):
            for method in ("CASH", "MPESA"):
                self.add(mode, quantity=1)
                payload = self.payload(mode, method)
                payload["reference"] = mode.upper()+"-REFERENCE" if method == "MPESA" else ""
                response = self.client.post(reverse("dashboard:pos_sale"), payload, follow=True)
                self.assertContains(response, "Payment Confirmed" if mode == "bookings" else "Sale completed successfully.")
                self.assertContains(response, "Your cart is empty")
                key = "pos_booking_cart" if mode == "bookings" else "pos_cart"
                self.assertEqual(self.client.session[key]["lines"], {})
                self.assertFalse(Order.objects.exclude(status="CONFIRMED").exists())
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(Payment.objects.filter(state="CONFIRMED").count(), 4)
        self.assertEqual(InventoryMovement.objects.count(), 4)

    def test_failed_payment_and_database_failure_preserve_cart(self):
        for mode in ("sales", "bookings"):
            self.add(mode)
            key = "pos_booking_cart" if mode == "bookings" else "pos_cart"
            before = self.client.session[key]
            payload = self.payload(mode, "MPESA")
            payload["reference"] = ""
            self.client.post(reverse("dashboard:pos_sale"), payload)
            self.assertEqual(self.client.session[key], before)
            with patch("apps.dashboard.pos_views.checkout_pos", side_effect=OperationalError("Timeout")):
                self.client.post(reverse("dashboard:pos_sale"), self.payload(mode))
            self.assertEqual(self.client.session[key], before)
        self.assertFalse(Order.objects.exists())

    def test_capacity_failure_after_cart_keeps_cart_and_rolls_back_payment(self):
        self.add(quantity=100)
        before = self.client.session["pos_booking_cart"]
        self.decrease("99")
        self.client.post(reverse("dashboard:pos_sale"), self.payload(method="MPESA"))
        self.assertEqual(self.client.session["pos_booking_cart"], before)
        for model in (Order, Payment, PaymentEvidence, Commitment):
            self.assertFalse(model.objects.exists())

    def test_zero_stock_alone_is_not_bookable_and_sales_cannot_be_bookings(self):
        response = self.client.get(reverse("dashboard:pos"), {"activity":"bookings"})
        self.assertEqual({entry["batch"].pk for entry in response.context["products"]}, {self.batch.pk})
        with self.assertRaises(ValidationError):
            self.checkout(activity="sales")
        with self.assertRaises(ValidationError):
            self.checkout(lines=[OrderLineInput(self.product.pk, self.unit.pk, 1, "PRE_ORDER")])

    def test_pending_booking_does_not_reserve_capacity_and_rechecks_on_payment(self):
        args = dict(channel="POS", fulfillment_method="CUSTOMER_COLLECTION", lines=[self.line(3500)],
                    location_id=self.bomet.pk, actor=self.actor, creation_idempotency_key=uuid.uuid4(), payment_method="CASH")
        order = create_pending_order(**args)
        self.assertEqual(remaining_capacity(self.batch), Decimal("3500.000"))
        self.checkout(lines=[self.line(1)])
        from apps.payments.pos import confirm_pos_payment
        with self.assertRaises(ValidationError):
            confirm_pos_payment(order_id=order.pk, method="CASH", reference="", actor=self.actor, idempotency_key=uuid.uuid4())
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING")

    def test_late_server_failure_rolls_back_sale_or_booking_and_retains_cart(self):
        from apps.payments.models import PaymentStatusEvent
        original_save = PaymentStatusEvent.save

        def fail_confirmation(event, *args, **kwargs):
            if event.new_state == "CONFIRMED":
                raise OperationalError("Failure after supply and payment writes")
            return original_save(event, *args, **kwargs)

        for mode in ("sales", "bookings"):
            self.add(mode)
            key = "pos_cart" if mode == "sales" else "pos_booking_cart"
            before = self.client.session[key]
            with patch.object(PaymentStatusEvent, "save", fail_confirmation):
                self.client.post(reverse("dashboard:pos_sale"), self.payload(mode, "MPESA"))
            self.assertEqual(self.client.session[key], before)
            for model in (Order, Payment, PaymentEvidence, PaymentVerificationAttempt, Commitment, Reservation, SourceAllocation):
                self.assertFalse(model.objects.exists(), model.__name__)
        self.assertEqual(InventoryMovement.objects.count(), 2)

    def test_confirmation_permissions_are_preserved_for_both_methods(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        cashier = get_user_model().objects.create_user(username="pos-only", is_staff=True)
        cashier.user_permissions.add(Permission.objects.get(content_type__app_label="pos", codename="process_sale"))
        for method in ("CASH", "MPESA"):
            with self.assertRaises(PermissionDenied):
                self.checkout(actor=cashier, method=method, reference="REF" if method == "MPESA" else "")
        self.assertFalse(Order.objects.exists())

    def test_unassigned_batch_can_be_assigned_with_audit(self):
        batch = self.make_batch(None, "UNASSIGNED-AUDIT", "500")
        updated = update_batch(batch_id=batch.pk, current_quantity=batch.current_quantity,
                               expected_ready_date=batch.expected_ready_date, notes="", reason="Assign actual branch",
                               location_id=self.bomet.pk, actor=self.actor, correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
        self.assertEqual(bookable_units(batch=updated, unit=self.unit, location_id=self.bomet.pk), 500)
        event = updated.history.get(operation="UPDATED")
        self.assertIsNone(event.previous_location_id)
        self.assertEqual(event.location_id, self.bomet.pk)
