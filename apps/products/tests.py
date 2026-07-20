from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.urls import reverse

from .mock_data import PRODUCTS


class ProductDiscoveryTests(SimpleTestCase):
    def test_shop_renders_shared_catalog_contract(self):
        response = self.client.get(reverse("products:shop"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["products"]), 12)
        self.assertContains(response, "Anna F1 Tomato")
        self.assertContains(response, "data-product-card", count=len(PRODUCTS))
        self.assertContains(response, "data-filter-open")
        self.assertContains(response, "data-pagination")

    def test_category_limits_products(self):
        response = self.client.get(reverse("products:category", args=["fruit-seedlings"]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["category_slug"] == "fruit-seedlings" for item in response.context["products"]))

    def test_empty_category_has_guidance(self):
        response = self.client.get(reverse("products:category", args=["herbs-ornamentals"]))
        self.assertContains(response, "No seedlings in this category yet")

    def test_search_renders_frontend_search_contract(self):
        response = self.client.get(reverse("products:search") + "?q=tomato")
        self.assertContains(response, "data-search-input")
        self.assertContains(response, "data-empty-state")
        self.assertContains(response, "data-error-state")
        self.assertContains(response, "data-loading-state")
        self.assertContains(response, 'hidden role="status" aria-label="Loading products"')

    def test_product_detail_contains_required_discovery_information(self):
        response = self.client.get(reverse("products:product_detail", args=["anna-f1-tomato"]))
        self.assertEqual(response.status_code, 200)
        for copy in ("Product specifications", "Planting guide", "Related seedlings", "Recently viewed"):
            self.assertContains(response, copy)
        self.assertNotContains(response, "Preferred branch")
        self.assertNotContains(response, "Availability by branch")
        self.assertEqual(len(response.context["branch_availability"]), 3)

    def test_unknown_catalog_objects_return_404(self):
        self.assertEqual(self.client.get(reverse("products:product_detail", args=["unknown-seedling"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("products:category", args=["unknown-category"])).status_code, 404)

    def test_phase_1c_exposes_shared_commerce_actions_without_checkout(self):
        for url in (reverse("products:shop"), reverse("products:product_detail", args=["hass-avocado"])):
            response = self.client.get(url)
            self.assertContains(response, "Add to cart")
            self.assertContains(response, "data-wishlist-toggle")
            self.assertNotContains(response, "Buy now")


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
        catalog = (Path(settings.BASE_DIR) / "docs" / "catalog" / "master-product-catalog.md").read_text()
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
