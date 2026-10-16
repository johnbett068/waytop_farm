from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from .views import dashboard


class EmptyOperationsRuntimeTests(TestCase):
    routes = (
        ("dashboard:orders", (), "No orders yet"),
        ("dashboard:order_detail", ("WTF-260716-1042",), "No persisted order"),
        ("dashboard:source_lots", (), "No production source lots yet"),
        ("dashboard:production_tasks", (), "No production tasks yet"),
        ("dashboard:production_exceptions", (), "No production exceptions yet"),
        ("dashboard:inventory_items", (), "No inventory items yet"),
        ("dashboard:inventory_item_detail", ("PLT-AVO-HASS",), "No persisted inventory item"),
        ("dashboard:inventory_lots", (), "No inventory lots yet"),
        ("dashboard:inventory_movements", (), "No inventory movements yet"),
        ("dashboard:inventory_receiving", (), "No inventory receipts yet"),
        ("dashboard:inventory_transfers", (), "No inventory transfers yet"),
        ("dashboard:inventory_counts", (), "No inventory counts yet"),
    )

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = get_user_model().objects.create_user(
            username="operations-test", password="strong-test-password", is_staff=True
        )
        cls.non_staff_user = get_user_model().objects.create_user(
            username="customer-test", password="strong-test-password"
        )
        cls.unprivileged_staff_user = get_user_model().objects.create_user(
            username="unprivileged-operations-test",
            password="strong-test-password",
            is_staff=True,
        )
        cls.staff_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="orders",
                codename="view",
            )
        )
        cls.staff_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="production",
                codename="view_operations",
            )
        )
        cls.staff_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="view",
            )
        )

        cls.staff_user.user_permissions.add(Permission.objects.get(content_type__app_label="pos", codename="process_sale"))

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

    def test_dashboard_renders_truthful_empty_projection_without_records(self):
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/dashboard.html")
        self.assertContains(response, "data-authoritative-empty")
        self.assertContains(response, "No operational data yet")
        self.assertContains(response, "Nothing is inferred, seeded, or fabricated")
        self.assertNotContains(response, "data-metric-card")

    def test_inventory_dashboard_is_live_and_truthful_without_stock(self):
        response = self.client.get(reverse("dashboard:inventory"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/inventory/dashboard_live.html")
        self.assertContains(response, "Saleable seedling stock")
        self.assertContains(response, "Operational supplies")
        self.assertContains(response, "No operational supplies recorded yet")
        self.assertContains(response, "Low-stock thresholds are not configured")
        self.assertContains(response, "Stock changes only through authoritative Inventory movements")
        self.assertContains(response, "does not create Production records or a second stock balance")

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
        self.assertContains(response, 'aria-controls="staff-mobile-nav"')
        self.assertContains(response, 'id="staff-mobile-nav"')
        self.assertContains(response, "View public catalog")
        for fabricated in (
            "Notifications, 3 unread", "POS <small>2</small>",
            "Orders <small>8</small>", "Production <small>6</small>",
            "Inventory <small>7</small>", "Quality approval requested",
        ):
            self.assertNotContains(response, fabricated)
        self.assertNotContains(response, "Daily Handover")
        self.assertNotContains(response, "daily handover")

    def test_primary_staff_navigation_has_valid_active_routes(self):
        for route, label in (
            ("dashboard:dashboard", "Dashboard"),
            ("dashboard:pos", "POS"),
            ("dashboard:orders", "Orders"),
            ("dashboard:production", "Production"),
            ("dashboard:inventory", "Inventory"),
        ):
            with self.subTest(route=route):
                url = reverse(route)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    f'href="{url}" class="is-active" aria-current="page"',
                )
                self.assertContains(response, label)

        catalog_url = reverse("products:shop")
        response = self.client.get(catalog_url)
        self.assertEqual(response.status_code, 200)

    def test_staff_workspace_requires_authentication_and_staff_status(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertRedirects(
            response,
            f'{reverse("accounts:login")}?next={reverse("dashboard:dashboard")}',
        )
        self.client.force_login(self.non_staff_user)
        self.assertEqual(
            self.client.get(reverse("dashboard:dashboard")).status_code,
            403,
        )
        self.client.force_login(self.unprivileged_staff_user)
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No operational data yet")
        self.assertNotContains(response, "data-metric-card")

    def test_out_of_scope_workflow_routes_remain_inactive(self):
        for path in (
            "/dashboard/procurement/",
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

    def test_inactive_staff_identity_is_denied_explicitly(self):
        request = RequestFactory().get(reverse("dashboard:dashboard"))
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_active=False,
            is_staff=True,
        )
        with self.assertRaises(PermissionDenied):
            dashboard(request)


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
