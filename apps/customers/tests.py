import uuid

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Product

from .admin import CustomerAdmin, CustomerAddressAdmin
from .models import Customer, CustomerAddress


class CustomerPersistenceTests(TestCase):
    def test_customer_creation_uses_uuid_and_timestamps(self):
        customer = Customer.objects.create(display_name="Acme Growers")
        self.assertIsInstance(customer.pk, uuid.UUID)
        self.assertIsNotNone(customer.created_at)
        self.assertIsNotNone(customer.updated_at)

    def test_display_name_is_required_and_surrounding_space_is_removed(self):
        with self.assertRaises(ValidationError):
            Customer.objects.create(display_name="   ")
        customer = Customer.objects.create(display_name="  Acme Growers  ")
        self.assertEqual(customer.display_name, "Acme Growers")

    def test_phone_and_email_are_optional_non_unique_contact_fields(self):
        first = Customer.objects.create(
            display_name="First contact",
            phone="+254 724 853 914",
            email="Shared@Example.com",
        )
        second = Customer.objects.create(
            display_name="Second contact",
            phone=first.phone,
            email=first.email,
        )
        contact_only_by_name = Customer.objects.create(display_name="Walk-up enquiry")
        self.assertEqual(first.phone, "+254724853914")
        self.assertEqual(second.email, "shared@example.com")
        self.assertEqual(contact_only_by_name.phone, "")
        self.assertEqual(contact_only_by_name.email, "")

    def test_email_receives_structural_validation_and_is_normalized(self):
        with self.assertRaises(ValidationError):
            Customer.objects.create(display_name="Invalid email", email="not-an-email")
        customer = Customer.objects.create(display_name="Valid email", email="Person@Example.com")
        self.assertEqual(customer.email, "person@example.com")

    def test_phone_is_normalized_to_kenyan_e164_and_invalid_values_are_rejected(self):
        customer = Customer.objects.create(display_name="Local contact", phone="0724 853 914")
        self.assertEqual(customer.phone, "+254724853914")
        for invalid in ("not a number", "+12025550123", "123"):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                Customer.objects.create(display_name="Invalid contact", phone=invalid)

    def test_customer_can_be_deactivated_without_losing_identity(self):
        customer = Customer.objects.create(display_name="Seasonal buyer")
        original_id = customer.pk
        customer.is_active = False
        customer.save()
        customer.refresh_from_db()
        self.assertEqual(customer.pk, original_id)
        self.assertFalse(customer.is_active)

    def test_customer_table_has_no_authentication_or_future_domain_shortcuts(self):
        field_names = {field.name for field in Customer._meta.get_fields()}
        forbidden = {
            "user", "password", "groups", "products", "product", "branch", "preferred_branch",
            "inventory", "production", "payments", "fulfillment",
        }
        self.assertTrue(forbidden.isdisjoint(field_names))
        self.assertFalse(any(field.name == "orders" and field.concrete for field in Customer._meta.get_fields()))
        self.assertFalse(issubclass(Customer, get_user_model()))
        self.assertFalse(any(field.related_model is Product for field in Customer._meta.get_fields()))

    def test_runtime_starts_without_seed_customers(self):
        self.assertEqual(Customer.objects.count(), 0)


class CustomerAddressTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(display_name="Address owner")

    def make_address(self, **overrides):
        values = {
            "customer": self.customer,
            "label": "Farm gate",
            "county": "Bomet",
            "town_or_area": "Bomet Town",
            "address_line": "Road and landmark details",
        }
        values.update(overrides)
        return CustomerAddress.objects.create(**values)

    def test_address_creation_and_customer_relationship(self):
        address = self.make_address(delivery_instructions="Call at the gate")
        self.assertIsInstance(address.pk, uuid.UUID)
        self.assertEqual(address.customer, self.customer)
        self.assertEqual(list(self.customer.addresses.all()), [address])
        self.assertTrue(address.is_active)

    def test_required_address_fields_are_validated(self):
        for field in ("county", "town_or_area", "address_line"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.make_address(**{field: "   "})

    def test_multiple_non_default_addresses_are_supported(self):
        first = self.make_address(label="Farm")
        second = self.make_address(label="Office", town_or_area="Sotik")
        self.assertEqual(self.customer.addresses.count(), 2)
        self.assertFalse(first.is_default)
        self.assertFalse(second.is_default)

    def test_only_one_active_default_address_is_allowed(self):
        self.make_address(is_default=True)
        with self.assertRaises(ValidationError):
            self.make_address(label="Second", town_or_area="Sotik", is_default=True)

    def test_inactive_address_cannot_be_default(self):
        with self.assertRaises(ValidationError):
            self.make_address(is_active=False, is_default=True)
        address = self.make_address(is_active=False, is_default=False)
        self.assertFalse(address.is_active)

    def test_address_relationship_protects_customer_deletion(self):
        self.make_address()
        with self.assertRaises(ProtectedError):
            self.customer.delete()
        self.customer.refresh_from_db()

    def test_address_has_no_branch_or_future_domain_relationship(self):
        field_names = {field.name for field in CustomerAddress._meta.get_fields()}
        self.assertTrue({"branch", "preferred_branch", "order", "fulfillment", "inventory"}.isdisjoint(field_names))


class CustomerAdminTests(TestCase):
    def test_models_are_registered_with_customer_only_admin(self):
        customer_admin = admin.site._registry[Customer]
        address_admin = admin.site._registry[CustomerAddress]
        self.assertIsInstance(customer_admin, CustomerAdmin)
        self.assertIsInstance(address_admin, CustomerAddressAdmin)
        self.assertEqual(customer_admin.inlines[0].model, CustomerAddress)
        self.assertNotIn("orders", customer_admin.list_display)
        self.assertNotIn("products", customer_admin.list_display)

    def test_admin_disables_destructive_customer_and_address_deletion(self):
        superuser = get_user_model().objects.create_superuser(
            username="customer-admin", password="strong-admin-password"
        )
        request = self.client.request().wsgi_request
        request.user = superuser
        self.assertFalse(admin.site._registry[Customer].has_delete_permission(request))
        self.assertFalse(admin.site._registry[CustomerAddress].has_delete_permission(request))

    def test_authorised_admin_can_open_customer_management(self):
        superuser = get_user_model().objects.create_superuser(
            username="customer-admin", password="strong-admin-password"
        )
        self.client.force_login(superuser)
        for model_name in ("customer", "customeraddress"):
            response = self.client.get(reverse(f"admin:customers_{model_name}_changelist"))
            self.assertEqual(response.status_code, 200)
