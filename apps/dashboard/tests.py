from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class EmptyOperationsRuntimeTests(TestCase):
    routes = (
        ("dashboard:dashboard", (), "No operational data yet"),
        ("dashboard:orders", (), "No orders yet"),
        ("dashboard:order_detail", ("WTF-260716-1042",), "No persisted order"),
        ("dashboard:production", (), "No production batches yet"),
        ("dashboard:source_lots", (), "No production source lots yet"),
        ("dashboard:production_batches", (), "No production batches yet"),
        ("dashboard:production_batch_detail", ("PB-AVO-2606-02",), "No persisted production batch"),
        ("dashboard:production_tasks", (), "No production tasks yet"),
        ("dashboard:production_exceptions", (), "No production exceptions yet"),
        ("dashboard:inventory", (), "No inventory records yet"),
        ("dashboard:inventory_items", (), "No inventory items yet"),
        ("dashboard:inventory_item_detail", ("PLT-AVO-HASS",), "No persisted inventory item"),
        ("dashboard:inventory_lots", (), "No inventory lots yet"),
        ("dashboard:inventory_movements", (), "No inventory movements yet"),
        ("dashboard:inventory_receiving", (), "No inventory receipts yet"),
        ("dashboard:inventory_transfers", (), "No inventory transfers yet"),
        ("dashboard:inventory_counts", (), "No inventory counts yet"),
        ("dashboard:inventory_adjustments", (), "No inventory adjustments yet"),
        ("dashboard:pos", (), "No POS orders or transactions yet"),
        ("dashboard:pos_sale", (), "No authoritative products or stock"),
    )

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = get_user_model().objects.create_user(
            username="operations-test", password="strong-test-password", is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff_user)

    def test_all_active_staff_routes_render_authoritative_empty_states(self):
        for route, args, copy in self.routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "dashboard/empty.html")
                self.assertContains(response, "data-authoritative-empty")
                self.assertContains(response, copy)
                self.assertContains(response, "Nothing is inferred, seeded, or fabricated")

    def test_state_query_cannot_reenable_populated_prototypes(self):
        fabricated = (
            "Jane Chebet", "WTF-260716-1042", "PB-AVO-2606-02",
            "LOT-AVO-2607-04", "KES 6,870", "KSh 84,650",
        )
        for route, args, _copy in self.routes:
            response = self.client.get(reverse(route, args=args) + "?state=success")
            for value in fabricated:
                self.assertNotContains(response, value)

    def test_navigation_and_notifications_have_no_fabricated_counts(self):
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertContains(response, "Notifications")
        self.assertContains(response, "No notifications yet")
        for fabricated in (
            "Notifications, 3 unread", "POS <small>2</small>",
            "Orders <small>8</small>", "Production <small>6</small>",
            "Inventory <small>7</small>", "Quality approval requested",
        ):
            self.assertNotContains(response, fabricated)
        self.assertNotContains(response, "Daily Handover")
        self.assertNotContains(response, "daily handover")

    def test_out_of_scope_workflow_routes_remain_inactive(self):
        for path in (
            "/dashboard/procurement/", "/dashboard/procurement/suppliers/",
            "/dashboard/delivery/", "/dashboard/delivery/jobs/",
            "/dashboard/pos/parked/", "/dashboard/pos/transactions/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_reusable_prototype_templates_are_retained_but_disconnected(self):
        templates = Path(settings.BASE_DIR) / "templates" / "dashboard"
        for relative in (
            "dashboard.html", "orders.html", "production/dashboard.html",
            "inventory/dashboard.html", "pos/dashboard.html",
            "procurement/dashboard.html", "delivery/dashboard.html",
        ):
            self.assertTrue((templates / relative).exists(), relative)


class EmptyStandaloneRuntimeTests(SimpleTestCase):
    def test_notifications_and_payments_are_empty(self):
        for route, message in (
            ("notifications:notifications", "No notifications yet"),
            ("payments:payment", "No payments yet"),
        ):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "data-runtime-empty-state")
            self.assertContains(response, message)
