"""Sales checkout regression coverage using Django's isolated database."""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse

from apps.dashboard import test_pos as fixtures
from apps.inventory.models import InventoryMovement, StockPosition, Reservation
from apps.orders.models import Order
from apps.orders.services import OrderLineInput
from apps.payments.models import Payment
from apps.payments.pos import checkout_pos


class SalesCleanupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.POSLocationTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.actor)

    add = fixtures.POSLocationTests.add
    payload = fixtures.POSLocationTests.payload

    def balances(self):
        return dict(StockPosition.objects.values_list("location_id", "on_hand_base_quantity"))

    def test_cash_and_mpesa_issue_stock_clear_cart_and_keep_branch(self):
        for method in ("CASH", "MPESA"):
            self.add(quantity=1)
            payload = self.payload()
            payload.update(payment_method=method, reference="" if method == "CASH" else "SALE-REF")
            before = self.balances()
            response = self.client.post(reverse("dashboard:pos_sale"), payload, follow=True)
            self.assertContains(response, "Sale completed successfully.")
            self.assertContains(response, "Your cart is empty.")
            self.assertNotContains(response, "Verify Payment")
            self.assertEqual(self.client.session["pos_cart"]["lines"], {})
            self.assertEqual(self.client.session["pos_cart"]["location"], str(self.bomet.pk))
            self.assertEqual(self.balances()[self.bomet.pk], before[self.bomet.pk] - 1)
            self.assertEqual(self.balances()[self.other.pk], before[self.other.pk])
            self.client.post(reverse("dashboard:pos_sale"), payload)
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(Payment.objects.filter(state="CONFIRMED").count(), 2)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 2)
        self.assertEqual(Reservation.objects.filter(state="CONSUMED").count(), 2)
        self.assertFalse(Order.objects.filter(customer__isnull=False).exists())

    def test_invalid_reference_preserves_cart_and_inventory(self):
        self.add()
        before, cart = self.balances(), self.client.session["pos_cart"]
        for reference in ("", "   ", "X" * 65):
            payload = self.payload()
            payload["reference"] = reference
            self.client.post(reverse("dashboard:pos_sale"), payload)
            self.assertEqual(self.client.session["pos_cart"], cart)
            self.assertEqual(self.balances(), before)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_failure_after_inventory_issue_rolls_back_everything(self):
        from apps.payments.pos import supply_ready_commitment
        self.add()
        cart, before = self.client.session["pos_cart"], self.balances()

        def fail_after_issue(**kwargs):
            supply_ready_commitment(**kwargs)
            raise OperationalError("Failure after ledger writes")

        with patch("apps.payments.pos.supply_ready_commitment", side_effect=fail_after_issue):
            self.client.post(reverse("dashboard:pos_sale"), self.payload())
        self.assertEqual(self.client.session["pos_cart"], cart)
        self.assertEqual(self.balances(), before)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertEqual(InventoryMovement.objects.count(), 2)

    def test_committed_checkout_retry_does_not_repeat_issue(self):
        args = dict(lines=[OrderLineInput(self.product.pk, self.unit.pk, 5, "READY")],
                    location_id=self.bomet.pk, customer=None, method="CASH", reference="",
                    actor=self.actor, idempotency_key=uuid.uuid4(), activity="sales")
        first = checkout_pos(**args)
        self.assertEqual(checkout_pos(**args).pk, first.pk)
        self.assertEqual(self.balances()[self.bomet.pk], Decimal("0"))
        self.assertEqual(self.balances()[self.other.pk], Decimal("20"))
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 1)
        self.assertEqual(Order.objects.count(), 1)

    def test_sale_copy_includes_unit_and_branch(self):
        response = self.add()
        self.assertContains(response, "5 Single seedling available at Bomet")
        self.assertContains(response, "Complete Sale")
        self.assertContains(response, "Enter the M-Pesa transaction reference to complete the sale.")
        self.assertNotContains(response, "Verify Payment")

    def test_committed_sale_with_old_browser_cart_recovers_without_duplicate(self):
        from apps.dashboard.pos_views import cart_lines
        self.add()
        cart = self.client.session["pos_cart"]
        payload = self.payload()
        checkout_pos(lines=cart_lines(cart["lines"]), location_id=self.bomet.pk,
                     customer=None, method="MPESA", reference=payload["reference"],
                     actor=self.actor, idempotency_key=uuid.UUID(cart["key"]), activity="sales")
        before = self.balances()
        response = self.client.post(reverse("dashboard:pos_sale"), payload, follow=True)
        self.assertContains(response, "Sale completed successfully.")
        self.assertEqual(self.client.session["pos_cart"]["lines"], {})
        self.assertEqual(self.balances(), before)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 1)

    def test_inventory_release_permission_is_not_bypassed(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        cashier = get_user_model().objects.create_user(username="cashier-no-release", is_staff=True)
        for app, code in (("pos", "process_sale"), ("payments", "verify"), ("commitments", "allocate")):
            cashier.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        self.client.force_login(cashier)
        self.add()
        cart, before = self.client.session["pos_cart"], self.balances()
        self.assertEqual(self.client.post(reverse("dashboard:pos_sale"), self.payload()).status_code, 403)
        self.assertEqual(self.client.session["pos_cart"], cart)
        self.assertEqual(self.balances(), before)
        self.assertFalse(Order.objects.exists())
