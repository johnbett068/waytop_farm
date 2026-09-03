from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import InventoryMovement, Reservation, SourceAllocation, StockPosition
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.production.forms import BatchCreateForm
from apps.production.models import ProductionBatch
from apps.production.services import create_batch

from .models import Product, ProductPrice, ProductSaleUnit
from .services import create_seedling_product


class StaffCatalogWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalog_staff = get_user_model().objects.create_user(
            username="catalog-staff", password="test-password", is_staff=True
        )
        cls.view_only_staff = get_user_model().objects.create_user(
            username="catalog-viewer", password="test-password", is_staff=True
        )
        cls.unprivileged_staff = get_user_model().objects.create_user(
            username="catalog-unprivileged", password="test-password", is_staff=True
        )
        cls.inactive_staff = get_user_model().objects.create_user(
            username="catalog-inactive", password="test-password", is_staff=True, is_active=False
        )
        for codename in (
            "view_product",
            "add_product",
            "add_productsaleunit",
            "add_productprice",
        ):
            cls.catalog_staff.user_permissions.add(
                Permission.objects.get(content_type__app_label="products", codename=codename)
            )
        cls.view_only_staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="products", codename="view_product")
        )

    def service_values(self, **overrides):
        values = {
            "name": "Anna F1 Tomato Seedling",
            "sku": "WTP-VEG-101",
            "slug": "anna-f1-tomato-seedling",
            "description": "A legitimate nursery seedling Product.",
            "base_inventory_unit": "seedling",
            "is_active": True,
            "is_published": True,
            "sale_unit_name": "Tray of 128",
            "sale_unit_base_quantity": Decimal("128.000"),
            "price_amount": Decimal("2500.00"),
            "price_effective_start": timezone.now(),
            "actor": self.catalog_staff,
        }
        values.update(overrides)
        return values

    def test_authoritative_workflow_creates_product_sale_unit_and_price_atomically(self):
        product, unit, price = create_seedling_product(**self.service_values())
        self.assertEqual(product.base_inventory_unit, "seedling")
        self.assertTrue(product.is_active)
        self.assertEqual(unit.product, product)
        self.assertEqual(unit.base_quantity, Decimal("128.000"))
        self.assertEqual(price.sale_unit, unit)
        self.assertEqual(price.amount, Decimal("2500.00"))
        self.assertEqual(price.currency, ProductPrice.Currency.KES)

    def test_slug_is_generated_and_optional_price_remains_supported(self):
        product, unit, price = create_seedling_product(
            **self.service_values(
                name="Cabbage Seedling",
                sku="WTP-VEG-102",
                slug="",
                is_published=False,
                price_amount=None,
                price_effective_start=None,
            )
        )
        self.assertEqual(product.slug, "cabbage-seedling")
        self.assertEqual(unit.product, product)
        self.assertIsNone(price)

    def test_active_product_appears_in_batch_dropdown_and_inactive_product_does_not(self):
        active, _unit, _price = create_seedling_product(**self.service_values())
        inactive, _unit, _price = create_seedling_product(
            **self.service_values(
                name="Inactive Seedling",
                sku="WTP-VEG-103",
                slug="inactive-seedling",
                is_active=False,
                is_published=False,
            )
        )
        choices = BatchCreateForm().fields["product"].queryset
        self.assertIn(active, choices)
        self.assertNotIn(inactive, choices)

    def test_batch_relationship_uses_canonical_product_and_never_duplicates_it(self):
        product, _unit, _price = create_seedling_product(**self.service_values())
        field = ProductionBatch._meta.get_field("product")
        self.assertIs(field.remote_field.model, Product)
        product_count = Product.objects.count()
        batch = create_batch(
            batch_number="PB-CATALOG-001",
            product_id=product.pk,
            start_date=timezone.localdate(),
            expected_ready_date=timezone.localdate(),
            quantity_started=Decimal("128.000"),
            notes="Canonical Product relationship",
            actor=self._production_actor(),
            correlation_id="d103f119-114c-4637-9ee0-667101ba857c",
            idempotency_key="3018d6cc-5bb4-45b9-85a1-94a7d7726614",
        )
        self.assertEqual(batch.product, product)
        self.assertEqual(Product.objects.count(), product_count)

    def _production_actor(self):
        actor = get_user_model().objects.create_user(
            username="catalog-production-operator", is_staff=True
        )
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="production", codename="manage_batches"
            )
        )
        return actor

    def test_existing_products_remain_unchanged_when_new_product_is_created(self):
        existing = Product.objects.create(
            sku="WTP-EXISTING-001", slug="existing-seedling", name="Existing Seedling",
            description="Preserve exactly", base_inventory_unit="seedling",
            is_active=True, is_published=False,
        )
        create_seedling_product(**self.service_values())
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Existing Seedling")
        self.assertEqual(existing.description, "Preserve exactly")
        self.assertTrue(existing.is_active)

    def test_product_creation_requires_existing_exact_permissions_and_active_staff(self):
        for actor in (None, self.view_only_staff, self.unprivileged_staff, self.inactive_staff):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                create_seedling_product(**self.service_values(actor=actor))
        superuser = get_user_model().objects.create_superuser("catalog-superuser", password=None)
        product, _unit, _price = create_seedling_product(
            **self.service_values(actor=superuser, sku="WTP-SUPER-001", slug="super-seedling")
        )
        self.assertEqual(product.name, "Anna F1 Tomato Seedling")

    def test_invalid_product_or_sale_unit_rolls_back_the_complete_workflow(self):
        with self.assertRaises(ValidationError):
            create_seedling_product(
                **self.service_values(is_active=False, is_published=True)
            )
        self.assertEqual(Product.objects.count(), 0)
        with self.assertRaises(ValidationError):
            create_seedling_product(
                **self.service_values(sale_unit_base_quantity=Decimal("0"))
            )
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(ProductSaleUnit.objects.count(), 0)

    def test_staff_ui_creates_catalog_product_and_lists_it(self):
        self.client.force_login(self.catalog_staff)
        response = self.client.post(reverse("dashboard:catalog_product_create"), {
            "name": "Sukuma Wiki Seedling",
            "sku": "WTP-VEG-104",
            "slug": "sukuma-wiki-seedling",
            "description": "Nursery-raised seedling.",
            "base_inventory_unit": "seedling",
            "is_active": "on",
            "is_published": "on",
            "sale_unit_name": "Tray of 128",
            "sale_unit_base_quantity": "128.000",
            "price_amount": "1800.00",
            "price_effective_start": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertRedirects(response, reverse("dashboard:catalog_products"))
        product = Product.objects.get(sku="WTP-VEG-104")
        listing = self.client.get(reverse("dashboard:catalog_products"))
        self.assertContains(listing, product.name)
        self.assertContains(listing, "Available for new batches")

    def test_staff_routes_enforce_view_and_create_permissions(self):
        self.client.force_login(self.view_only_staff)
        self.assertEqual(self.client.get(reverse("dashboard:catalog_products")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:catalog_product_create")).status_code, 403)
        self.client.force_login(self.unprivileged_staff)
        self.assertEqual(self.client.get(reverse("dashboard:catalog_products")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:catalog_products")).status_code, 302)

    def test_catalog_creation_has_no_inventory_or_commerce_side_effects(self):
        before = (
            StockPosition.objects.count(), InventoryMovement.objects.count(), Reservation.objects.count(),
            SourceAllocation.objects.count(), Order.objects.count(), Payment.objects.count(),
            ProductionBatch.objects.count(),
        )
        create_seedling_product(**self.service_values())
        after = (
            StockPosition.objects.count(), InventoryMovement.objects.count(), Reservation.objects.count(),
            SourceAllocation.objects.count(), Order.objects.count(), Payment.objects.count(),
            ProductionBatch.objects.count(),
        )
        self.assertEqual(after, before)

    def test_published_product_remains_visible_through_existing_customer_catalog(self):
        product, _unit, _price = create_seedling_product(**self.service_values())
        shop = self.client.get(reverse("products:shop"))
        detail = self.client.get(reverse("products:product_detail", args=(product.slug,)))
        self.assertContains(shop, product.name)
        self.assertContains(detail, "Tray of 128")
        self.assertContains(detail, "KES 2500.00")

