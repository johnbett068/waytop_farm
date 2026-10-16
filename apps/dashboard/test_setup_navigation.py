from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.inventory.models import InventoryLocation


class SetupNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser("setup-nav", "setup@example.com", "test")
        cls.location = InventoryLocation.objects.create(code="SETUP-NAV", name="Test site")

    def setUp(self):
        self.client.force_login(self.actor)

    def test_inventory_tabs_and_setup_are_separate(self):
        response = self.client.get(reverse("dashboard:inventory"))
        html = response.content.decode()
        tabs = html.split('<section class="inventory-shortcuts"', 1)[1].split('</section>', 1)[0]
        for label in ("Overview", "On-Hand Stock", "Acquire Stock", "History"):
            self.assertIn(label, tabs)
        for label in ("Suppliers", "Locations", "Setup"):
            self.assertNotIn(label, tabs)
        setup = html.split('aria-label="Setup navigation">', 1)[1].split('</div>', 1)[0]
        self.assertIn("Locations / Branches", setup)
        self.assertIn("Suppliers", setup)
        self.assertNotIn("Acquire Stock", setup)

    def test_management_and_legacy_routes_keep_setup_context(self):
        for route, args in (
            ("inventory_location_list", ()), ("inventory_location_create", ()),
            ("inventory_location_edit", (self.location.pk,)),
            ("inventory_supplier_list", ()), ("inventory_supplier_create", ()),
            ("procurement_supplier_list", ()), ("procurement_supplier_create", ()),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(f"dashboard:{route}", args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<p>Setup</p>')
                self.assertNotContains(response, 'aria-label="Inventory sections"')
                self.assertContains(response, 'aria-current="page"')

    def test_setup_links_follow_existing_view_permissions(self):
        user = get_user_model().objects.create_user(username="setup-restricted", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertNotContains(response, 'aria-label="Setup navigation"')
        for route in ("inventory_supplier_list", "inventory_location_list"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{route}")).status_code, 403)
        user.user_permissions.add(Permission.objects.get(content_type__app_label="procurement", codename="view"))
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertContains(response, reverse("dashboard:inventory_supplier_list"))
        self.assertNotContains(response, reverse("dashboard:inventory_location_list"))
