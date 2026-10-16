import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.inventory.forms import StockAcquisitionForm
from .models import Supplier


class SupplierScreenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(username="supplier-manager", is_staff=True)
        cls.actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="inventory", codename="view"),
            Permission.objects.get(content_type__app_label="procurement", codename="manage_suppliers"),
        )

    def setUp(self):
        self.client.force_login(self.actor)

    def data(self, **extra):
        return {"name": "Local Nursery", "correlation_id": uuid.uuid4(),
                "idempotency_key": uuid.uuid4(), **extra}

    def test_create_name_only_and_retry(self):
        data = self.data()
        for _ in range(2):
            self.assertRedirects(self.client.post(reverse("dashboard:inventory_supplier_create"), data),
                                 reverse("dashboard:inventory_supplier_list"))
        supplier = Supplier.objects.get()
        self.assertEqual(supplier.name, "Local Nursery")
        for field in ("contact_person", "phone", "email", "address", "notes"):
            self.assertEqual(getattr(supplier, field), "")
        self.assertIn(supplier, StockAcquisitionForm().fields["supplier"].queryset)

    def test_create_all_optional_fields_and_view_details(self):
        values = dict(contact_person="Jane", phone="0700000000", email="jane@example.com",
                      address="Nursery Road", notes="Call on arrival")
        self.client.post(reverse("dashboard:inventory_supplier_create"), self.data(**values))
        supplier = Supplier.objects.get()
        response = self.client.get(reverse("dashboard:inventory_supplier_list"))
        for field, value in values.items():
            self.assertEqual(getattr(supplier, field), value)
            self.assertContains(response, value)

    def test_edit_preserves_identity_and_can_clear_optional_fields(self):
        self.client.post(reverse("dashboard:inventory_supplier_create"), self.data(phone="0700000000"))
        supplier = Supplier.objects.get()
        original_code = supplier.code
        self.assertRedirects(self.client.post(
            reverse("dashboard:inventory_supplier_edit", args=(supplier.pk,)),
            self.data(name="Updated Nursery")), reverse("dashboard:inventory_supplier_list"))
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, "Updated Nursery")
        self.assertEqual(supplier.phone, "")
        self.assertEqual(supplier.code, original_code)
        self.assertEqual(Supplier.objects.count(), 1)

    def test_name_required_and_email_validation(self):
        for extra, field in (({"name": "  "}, "name"), ({"email": "invalid"}, "email")):
            response = self.client.post(reverse("dashboard:inventory_supplier_create"), self.data(**extra))
            self.assertIn(field, response.context["form"].errors)
        self.assertFalse(Supplier.objects.exists())

    def test_form_fields_and_inventory_navigation(self):
        response = self.client.get(reverse("dashboard:inventory_supplier_create"))
        self.assertEqual([field.name for field in response.context["form"].visible_fields()],
                         ["name", "contact_person", "phone", "email", "address", "notes"])
        self.assertContains(response, "Save Supplier")
        self.assertContains(response, reverse("dashboard:inventory_supplier_list"))
        self.assertNotContains(response, reverse("dashboard:procurement_purchase_list"))

    def test_viewer_cannot_edit_supplier(self):
        viewer = get_user_model().objects.create_user(username="supplier-viewer", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label="inventory", codename="view"))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("dashboard:inventory_supplier_list")).status_code, 200)
        self.assertEqual(self.client.post(reverse("dashboard:inventory_supplier_create"), self.data()).status_code, 403)
        self.assertFalse(Supplier.objects.exists())
