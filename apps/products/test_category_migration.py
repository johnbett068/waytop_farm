import importlib
import uuid

from django.test import SimpleTestCase


migration = importlib.import_module(
    "apps.products.migrations.0002_product_category_and_sku_sequence"
)


class ProductCategoryMigrationDecisionTests(SimpleTestCase):
    def test_recognized_skus_map_to_their_exact_categories(self):
        product_id = uuid.uuid4()
        self.assertEqual(
            migration.category_and_suffix_for_existing_product(product_id, "WTP-VEG-007"),
            ("VEG", 7),
        )
        self.assertEqual(
            migration.category_and_suffix_for_existing_product(product_id, "WTP-FRT-021"),
            ("FRT", 21),
        )
        self.assertEqual(
            migration.category_and_suffix_for_existing_product(product_id, "WTP-TRE-1000"),
            ("TRE", 1000),
        )

    def test_ratified_tomato_seedling_maps_to_vegetable_without_changing_its_sku(self):
        sku = "TOMATO SEEDLING"
        resolution = migration.category_and_suffix_for_existing_product(
            uuid.UUID("8de0cae8-7a0f-4729-b1c8-9f4fc2c2ecb2"), sku
        )
        self.assertEqual(resolution, ("VEG", None))
        self.assertEqual(sku, "TOMATO SEEDLING")

    def test_unknown_sku_format_is_not_classified(self):
        self.assertIsNone(
            migration.category_and_suffix_for_existing_product(
                uuid.uuid4(), "UNRATIFIED PRODUCT"
            )
        )
