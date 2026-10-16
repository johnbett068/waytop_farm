from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .catalog import commerce_catalog_projection, public_catalog_products
from .mock_data import PRODUCTS
from .models import Product, ProductPrice, ProductSaleUnit


def make_product(**overrides):
    values = {
        "sku": "WTP-REAL-001",
        "slug": "persistent-seedling",
        "name": "Persistent Seedling",
        "category": Product.Category.VEGETABLE,
        "description": "An authoritative catalog description.",
        "base_inventory_unit": "seedling",
        "is_active": True,
        "is_published": True,
    }
    values.update(overrides)
    return Product.objects.create(**values)


class ProductPersistenceTests(TestCase):
    def test_product_can_be_created_with_stable_uuid(self):
        product = make_product()
        self.assertIsNotNone(product.pk)
        self.assertEqual(product.base_inventory_unit, "seedling")

    def test_sku_and_slug_are_unique(self):
        make_product()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_product(slug="another", name="Duplicate SKU")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_product(sku="WTP-REAL-002", name="Duplicate slug")

    def test_inactive_product_cannot_be_published(self):
        product = Product(
            sku="WTP-REAL-003", slug="invalid-publication", name="Invalid",
            category=Product.Category.VEGETABLE,
            base_inventory_unit="seedling", is_active=False, is_published=True,
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_active_unpublished_and_inactive_unpublished_are_valid(self):
        active = make_product(is_published=False)
        inactive = make_product(
            sku="WTP-REAL-004", slug="inactive", name="Inactive",
            is_active=False, is_published=False,
        )
        active.full_clean()
        inactive.full_clean()

    def test_product_has_no_future_domain_fields(self):
        field_names = {field.name for field in Product._meta.get_fields()}
        self.assertTrue({"stock", "available_quantity", "branch", "location", "cost", "production_quantity"}.isdisjoint(field_names))


class ProductSaleUnitTests(TestCase):
    def setUp(self):
        self.product = make_product()

    def test_sale_unit_belongs_to_product_and_multiple_units_are_supported(self):
        individual = ProductSaleUnit.objects.create(product=self.product, name="Individual", base_quantity=1)
        tray = ProductSaleUnit.objects.create(product=self.product, name="Tray", base_quantity=128)
        self.assertEqual(individual.product, self.product)
        self.assertEqual(list(self.product.sale_units.all()), [individual, tray])

    def test_sale_unit_quantity_must_be_positive(self):
        unit = ProductSaleUnit(product=self.product, name="Invalid", base_quantity=0)
        with self.assertRaises(ValidationError):
            unit.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductSaleUnit.objects.create(product=self.product, name="Negative", base_quantity=-1)

    def test_sale_unit_names_are_unique_per_product(self):
        ProductSaleUnit.objects.create(product=self.product, name="Tray", base_quantity=128)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductSaleUnit.objects.create(product=self.product, name="Tray", base_quantity=64)


class ProductPriceTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.unit = ProductSaleUnit.objects.create(product=self.product, name="Individual", base_quantity=1)
        self.now = timezone.now()

    def test_price_belongs_to_sale_unit_zero_is_valid_and_currency_is_stored(self):
        price = ProductPrice.objects.create(
            sale_unit=self.unit, amount=0, currency="KES", effective_start=self.now,
        )
        self.assertEqual(price.sale_unit, self.unit)
        self.assertEqual(price.amount, Decimal("0"))
        self.assertEqual(price.currency, "KES")

    def test_negative_price_and_unsupported_currency_are_rejected(self):
        with self.assertRaises(ValidationError):
            ProductPrice.objects.create(sale_unit=self.unit, amount=-1, effective_start=self.now)
        with self.assertRaises(ValidationError):
            ProductPrice.objects.create(sale_unit=self.unit, amount=10, currency="USD", effective_start=self.now)

    def test_effective_end_must_follow_start(self):
        with self.assertRaises(ValidationError):
            ProductPrice.objects.create(
                sale_unit=self.unit, amount=10, effective_start=self.now, effective_end=self.now,
            )

    def test_history_is_preserved_and_touching_periods_do_not_overlap(self):
        old = ProductPrice.objects.create(
            sale_unit=self.unit,
            amount=10,
            effective_start=self.now - timedelta(days=10),
            effective_end=self.now - timedelta(days=5),
        )
        current = ProductPrice.objects.create(
            sale_unit=self.unit,
            amount=12,
            effective_start=old.effective_end,
        )
        self.assertEqual(ProductPrice.objects.filter(sale_unit=self.unit).count(), 2)
        self.assertNotEqual(old.pk, current.pk)
        old.refresh_from_db()
        self.assertEqual(old.amount, Decimal("10.00"))

    def test_existing_price_amount_cannot_be_overwritten(self):
        price = ProductPrice.objects.create(
            sale_unit=self.unit, amount=10, effective_start=self.now,
        )
        price.amount = 12
        with self.assertRaises(ValidationError):
            price.save()
        price.refresh_from_db()
        self.assertEqual(price.amount, Decimal("10.00"))

    def test_overlapping_active_price_periods_are_rejected(self):
        ProductPrice.objects.create(
            sale_unit=self.unit, amount=10,
            effective_start=self.now - timedelta(days=2), effective_end=self.now + timedelta(days=2),
        )
        with self.assertRaises(ValidationError):
            ProductPrice.objects.create(
                sale_unit=self.unit, amount=11,
                effective_start=self.now - timedelta(days=1), effective_end=self.now + timedelta(days=3),
            )


class PublicCatalogTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.product = make_product()
        self.unit = ProductSaleUnit.objects.create(product=self.product, name="Individual", base_quantity=1)
        self.price = ProductPrice.objects.create(
            sale_unit=self.unit, amount=Decimal("25.50"), effective_start=self.now - timedelta(hours=1),
        )

    def test_only_active_published_products_are_returned(self):
        make_product(sku="WTP-HIDDEN-001", slug="unpublished", name="Unpublished", is_published=False)
        make_product(sku="WTP-HIDDEN-002", slug="inactive", name="Inactive", is_active=False, is_published=False)
        self.assertEqual([product.slug for product in public_catalog_products(at=self.now)], [self.product.slug])

    def test_only_active_units_and_applicable_prices_are_returned(self):
        inactive_unit = ProductSaleUnit.objects.create(product=self.product, name="Inactive tray", base_quantity=128, is_active=False)
        ProductPrice.objects.create(
            sale_unit=inactive_unit, amount=100, effective_start=self.now - timedelta(hours=1),
        )
        expired_unit = ProductSaleUnit.objects.create(product=self.product, name="Old bundle", base_quantity=10)
        ProductPrice.objects.create(
            sale_unit=expired_unit, amount=50,
            effective_start=self.now - timedelta(days=2), effective_end=self.now - timedelta(days=1),
        )
        product = public_catalog_products(at=self.now)[0]
        self.assertEqual([unit.name for unit in product.catalog_sale_units], ["Individual", "Old bundle"])
        self.assertEqual(product.catalog_sale_units[0].catalog_price, self.price)
        self.assertIsNone(product.catalog_sale_units[1].catalog_price)
        projection = commerce_catalog_projection([product])
        self.assertEqual([unit["name"] for unit in projection[0]["sale_units"]], ["Individual"])

    def test_shop_and_detail_render_persistent_commercial_data(self):
        shop = self.client.get(reverse("products:shop"))
        detail = self.client.get(reverse("products:product_detail", args=(self.product.slug,)))
        self.assertContains(shop, self.product.name)
        self.assertContains(shop, "From KES 25.50")
        self.assertContains(detail, "Individual")
        self.assertContains(detail, "KES 25.50")
        self.assertNotContains(detail, "In stock")
        self.assertNotContains(detail, "Preferred branch")
        self.assertNotContains(detail, "Production batch")

    def test_unpublished_and_inactive_products_return_404(self):
        unpublished = make_product(sku="WTP-HIDDEN-003", slug="hidden", name="Hidden", is_published=False)
        self.assertEqual(self.client.get(reverse("products:product_detail", args=(unpublished.slug,))).status_code, 404)

    def test_search_is_server_backed(self):
        response = self.client.get(reverse("products:search"), {"q": "Persistent"})
        self.assertContains(response, self.product.name)
        self.assertContains(response, "1 result")

    def test_runtime_does_not_require_mock_catalog(self):
        self.assertNotEqual(self.product.slug, PRODUCTS[0]["slug"])
        response = self.client.get(reverse("products:shop"))
        self.assertNotContains(response, PRODUCTS[0]["name"])

    def test_public_projection_excludes_internal_domains_and_inventory(self):
        payload = commerce_catalog_projection(public_catalog_products(at=self.now))[0]
        self.assertTrue({"stock", "availability", "branch", "location", "cost", "inventory", "production"}.isdisjoint(payload))


class EmptyCatalogTests(TestCase):
    def test_empty_database_produces_valid_empty_states(self):
        shop = self.client.get(reverse("products:shop"))
        home = self.client.get(reverse("core:home"))
        self.assertEqual(shop.context["products"], [])
        self.assertEqual(shop.context["commerce_catalog"], [])
        self.assertContains(shop, "No products match your selection")
        self.assertContains(home, "No products published yet")

    def test_unknown_product_and_unimplemented_category_return_404(self):
        self.assertEqual(self.client.get(reverse("products:product_detail", args=("unknown",))).status_code, 404)
        self.assertEqual(self.client.get(reverse("products:category", args=("unknown",))).status_code, 404)


class ProductAdminTests(TestCase):
    def test_all_catalog_models_are_available_to_authorised_admin(self):
        admin_user = get_user_model().objects.create_superuser(username="catalog-admin", password="safe-test-password")
        self.client.force_login(admin_user)
        for model_name in ("product", "productsaleunit", "productprice"):
            response = self.client.get(reverse(f"admin:products_{model_name}_changelist"))
            self.assertEqual(response.status_code, 200)


class MasterCatalogContractTests(SimpleTestCase):
    required_fields = {
        "name", "variety", "category", "price", "unit", "stock", "stock_label",
        "available_branches", "image_filename", "planting_guide", "growing_guide",
        "short", "recommended_regions", "sku", "catalog_version",
    }

    def test_every_product_has_complete_unique_catalog_identity(self):
        slugs = [product["slug"] for product in PRODUCTS]
        images = [product["image_filename"] for product in PRODUCTS]
        skus = [product["sku"] for product in PRODUCTS]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(len(images), len(set(images)))
        self.assertEqual(len(skus), len(set(skus)))
        for product in PRODUCTS:
            self.assertFalse(self.required_fields - product.keys(), product["slug"])
            self.assertTrue(product["available_branches"], product["slug"])

    def test_every_product_uses_an_individual_existing_webp(self):
        for product in PRODUCTS:
            self.assertTrue(product["image_filename"].endswith(".webp"))
            self.assertNotIn("sprite", product["image_filename"])
            self.assertIsNotNone(finders.find(product["image_filename"]), product["image_filename"])

    def test_master_document_contains_every_governed_product_and_image(self):
        catalog = (Path(settings.BASE_DIR) / "docs" / "catalog" / "master-product-catalog.md").read_text(encoding="utf-8")
        for product in PRODUCTS:
            self.assertIn(product["name"], catalog)
            self.assertIn(product["image_filename"], catalog)

    def test_declared_category_counts_match_catalog(self):
        from .mock_data import CATEGORIES
        for category in CATEGORIES:
            actual = sum(product["category_slug"] == category["slug"] for product in PRODUCTS)
            self.assertEqual(category["count"], actual, category["slug"])

    def test_removed_inaccurate_names_do_not_return(self):
        names = {product["name"] for product in PRODUCTS}
        self.assertNotIn("Fordhook Giant Spinach", names)
        self.assertNotIn("Gloria F1 Cabbage", names)
