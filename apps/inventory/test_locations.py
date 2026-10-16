import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Product
from .forms import StockAcquisitionForm
from .models import ExternalStockAcquisition, InventoryItem, InventoryLocation, InventoryMovement, StockPosition


class LocationManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(username="location-manager", is_staff=True)
        cls.actor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="inventory",
            codename__in=("view", "receive", "add_inventorylocation", "change_inventorylocation"),
        ))
        cls.product = Product.objects.create(
            name="Tomato Seedling", sku="TOMATO SEEDLING", slug="tomato-seedling",
            category=Product.Category.VEGETABLE, base_inventory_unit="seedling",
        )

    def setUp(self):
        self.client.force_login(self.actor)

    def create_location(self):
        data = {"name": "Test Branch", "idempotency_key": uuid.uuid4()}
        for _ in range(2):
            self.assertRedirects(self.client.post(reverse("dashboard:inventory_location_create"), data),
                                 reverse("dashboard:inventory_location_list"))
        return InventoryLocation.objects.get()

    def test_create_with_name_only_persists_once_without_stock(self):
        location = self.create_location()
        self.assertEqual(location.name, "Test Branch")
        self.assertTrue(location.code)
        self.assertTrue(location.is_active)
        self.assertTrue(location.allows_saleable_stock)
        self.assertFalse(StockPosition.objects.exists())
        self.assertFalse(InventoryItem.objects.exists())
        self.assertContains(self.client.get(reverse("dashboard:inventory_location_list")), location.name)

    def test_edit_preserves_identity_and_internal_policies(self):
        location = self.create_location()
        location.is_active = False
        location.allows_saleable_stock = False
        location.save()
        code = location.code
        response = self.client.post(reverse("dashboard:inventory_location_edit", args=(location.pk,)),
                                    {"name": "Renamed Site", "idempotency_key": uuid.uuid4()})
        self.assertRedirects(response, reverse("dashboard:inventory_location_list"))
        location.refresh_from_db()
        self.assertEqual(location.name, "Renamed Site")
        self.assertEqual(location.code, code)
        self.assertFalse(location.is_active)
        self.assertFalse(location.allows_saleable_stock)

    def test_name_is_required_and_only_business_field(self):
        url = reverse("dashboard:inventory_location_create")
        response = self.client.get(url)
        self.assertEqual([field.name for field in response.context["form"].visible_fields()], ["name"])
        for name in ("", "   ", "x" * 161):
            response = self.client.post(url, {"name": name, "idempotency_key": uuid.uuid4()})
            self.assertIn("name", response.context["form"].errors)
        self.assertFalse(InventoryLocation.objects.exists())

    def test_location_dropdown_preserves_active_rule_without_saleability_filter(self):
        location = self.create_location()
        location.allows_saleable_stock = False
        location.save()
        inactive = InventoryLocation.objects.create(code="INACTIVE", name="Closed site", is_active=False)
        response = self.client.get(reverse("dashboard:inventory_receipt_create"))
        field = response.context["form"].fields["location"]
        self.assertTrue(field.required)
        self.assertIn(location, field.queryset)
        self.assertNotIn(inactive, field.queryset)
        self.assertContains(response, '<select name="location"')
        self.assertContains(response, f'<option value="{location.pk}">{location.name}</option>', html=True)
        self.assertIn(self.product, response.context["form"].fields["product"].queryset)
        self.assertFalse(response.context["form"].fields["supplier"].required)

    def test_acquisition_at_created_location_and_rename_preserve_ledger(self):
        location = self.create_location()
        data = dict(product=self.product.pk, quantity="4.000", unit_cost="12.50",
                    acquisition_date="2026-09-08", supplier="", location=location.pk,
                    supplier_batch_reference="SITE-LOT", condition="SALEABLE", correlation_id=uuid.uuid4(),
                    idempotency_key=uuid.uuid4())
        for _ in range(2):
            self.assertRedirects(self.client.post(reverse("dashboard:inventory_receipt_create"), data),
                                 reverse("dashboard:inventory_stock"))
        acquisition = ExternalStockAcquisition.objects.get()
        self.assertIsNone(acquisition.supplier)
        self.assertEqual(acquisition.movement_line.destination_location, location)
        self.assertEqual(acquisition.movement.movement_type, InventoryMovement.Type.RECEIPT)
        position = StockPosition.objects.get()
        self.assertEqual(position.location, location)
        self.assertEqual(position.on_hand_base_quantity, Decimal("4.000"))
        self.assertEqual(InventoryItem.objects.filter(product=self.product).count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        for route in ("dashboard:inventory_stock", "dashboard:inventory_history"):
            response = self.client.get(reverse(route))
            self.assertContains(response, location.name)
            self.assertContains(response, self.product.name)
        self.client.post(reverse("dashboard:inventory_location_edit", args=(location.pk,)),
                         {"name": "Updated Site Name", "idempotency_key": uuid.uuid4()})
        acquisition.refresh_from_db()
        self.assertEqual(acquisition.movement_line.destination_location_id, location.pk)
        self.assertEqual(acquisition.movement_line.quantity, Decimal("4.000"))
        self.assertEqual(acquisition.unit_cost, Decimal("12.50"))
        self.assertContains(self.client.get(reverse("dashboard:inventory_history")), "Updated Site Name")

    def test_missing_location_lot_or_condition_still_invalid(self):
        location = self.create_location()
        for missing in ("location", "condition"):
            data = dict(product=self.product.pk, quantity="1.000", unit_cost="1.00",
                        acquisition_date="2026-09-08", location=location.pk, supplier_batch_reference="LOT",
                        condition="SALEABLE", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
            data[missing] = ""
            form = StockAcquisitionForm(data)
            self.assertFalse(form.is_valid())
            self.assertIn(missing, form.errors)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_inventory_view_does_not_grant_location_write_permissions(self):
        location = self.create_location()
        viewer = get_user_model().objects.create_user(username="location-viewer", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label="inventory", codename="view"))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("dashboard:inventory_location_list")).status_code, 200)
        for url in (reverse("dashboard:inventory_location_create"),
                    reverse("dashboard:inventory_location_edit", args=(location.pk,))):
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"name": "Denied", "idempotency_key": uuid.uuid4()}).status_code, 403)
        location.refresh_from_db()
        self.assertEqual(location.name, "Test Branch")
        self.assertEqual(InventoryLocation.objects.count(), 1)

    def test_setup_navigation_includes_locations_without_inventory_tabs(self):
        response = self.client.get(reverse("dashboard:inventory_location_list"))
        for route in ("inventory", "inventory_supplier_list", "inventory_location_list"):
            self.assertContains(response, reverse(f"dashboard:{route}"))
        self.assertNotContains(response, reverse("dashboard:procurement_purchase_list"))
        self.assertNotContains(response, 'aria-label="Inventory sections"')
        self.assertContains(response, 'aria-label="Setup navigation"')
        self.assertContains(response, "Locations / Branches")
