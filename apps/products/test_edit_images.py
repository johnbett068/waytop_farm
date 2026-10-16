"""Edit workflow regressions; Django test database and temporary media only."""
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import test_images as existing
from .catalog import public_catalog_products
from .image_validation import MAX_IMAGE_BYTES
from .models import Product, ProductImage, ProductPrice, ProductSaleUnit


class ProductEditImageTests(TestCase):
    setUpTestData = classmethod(existing.ProductImageTests.setUpTestData.__func__)
    upload = existing.ProductImageTests.upload

    def setUp(self):
        existing.ProductImageTests.setUp(self)
        self.url = reverse("dashboard:catalog_product_edit", args=[self.product.pk])
        self.client.force_login(self.actor)

    def values(self, **overrides):
        result = dict(action="save_product", name="Updated seedling", description="Staff description",
                      category="VEG", base_inventory_unit="seedling", is_active="on", is_published="on")
        result.update(overrides)
        return result

    def test_list_edit_links_for_every_status_and_readiness(self):
        for index, (active, published) in enumerate(((True, False), (False, False), (True, True))):
            Product.objects.create(name=f"Status {index}", sku=f"STATUS-{index}", slug=f"status-{index}",
                                   category="VEG", base_inventory_unit="seedling", is_active=active, is_published=published)
        unit = ProductSaleUnit.objects.create(product=self.product, name="Single", base_quantity=1)
        from apps.inventory.models import InventoryItem
        InventoryItem.objects.create(product=self.product, base_unit="seedling")
        ProductPrice.objects.create(sale_unit=unit, amount=25, effective_start=timezone.now()-timedelta(days=1))
        response = self.client.get(reverse("dashboard:catalog_products"))
        for product in Product.objects.all():
            self.assertContains(response, f'href="{reverse("dashboard:catalog_product_edit", args=[product.pk])}">Edit</a>')
        self.assertContains(response, "POS Ready")
        self.assertContains(response, "Not ready")

    def test_edit_displays_product_selling_images_and_guidance(self):
        image = self.upload(alt="Existing photo")
        ProductSaleUnit.objects.create(product=self.product, name="Tray", base_quantity=128)
        response = self.client.get(self.url)
        for text in (self.product.name, self.product.sku, "Tray", "128", image.image.url, "Existing photo",
                     "Product information", "How this Product is sold", "Product Images", "Price settings",
                     "960 \u00d7 768", "5:4", str(MAX_IMAGE_BYTES), "15 MiB", "GIF also supported"):
            self.assertContains(response, text)
        self.assertContains(response, "product-image-preview.js")

    test_upload_metadata_delete = existing.ProductImageTests.test_staff_upload_edit_delete_and_preview
    test_wrong_product_is_protected = existing.ProductImageTests.test_wrong_product_image_cannot_be_deleted_or_reordered
    test_invalid_upload_and_order = existing.ProductImageTests.test_invalid_upload_and_order_errors_render_without_creating_records
    def test_nonstaff_inactive_anonymous(self):
        self.client.logout()
        existing.ProductImageTests.test_anonymous_nonstaff_and_inactive_users_cannot_change_images(self)

    def test_oversized_and_storage_failure_leave_images_unchanged(self):
        image = self.upload()
        before = list(ProductImage.objects.values())
        upload = existing.image_upload()
        upload = SimpleUploadedFile("large.png", upload.read() + b"0" * MAX_IMAGE_BYTES)
        response = self.client.post(self.url, {"action":"upload_image", "upload-image":upload,
                                              "upload-sort_order":0})
        self.assertTrue(response.context["upload_form"].errors)
        with patch("django.core.files.storage.FileSystemStorage._save", side_effect=OSError("disk unavailable")):
            response = self.client.post(self.url, {"action":"upload_image", "upload-image":existing.image_upload(),
                                                  "upload-sort_order":0})
        self.assertContains(response, "could not be stored")
        self.assertEqual(list(ProductImage.objects.values()), before)
        self.assertTrue(image.image.storage.exists(image.image.name))

    def test_reorder_delete_promote_public_main_without_product_changes(self):
        first, second = self.upload(order=1), self.upload(order=2)
        before = Product.objects.values().get(pk=self.product.pk)
        self.client.post(self.url, {"action":"update_image", "image_id":second.pk,
                                   f"image-{second.pk}-alt_text":"Second", f"image-{second.pk}-sort_order":0})
        self.assertEqual(public_catalog_products()[0].catalog_main_image["url"], second.image.url)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {"action":"delete_image", "image_id":second.pk})
        self.assertEqual(public_catalog_products()[0].catalog_main_image["url"], first.image.url)
        self.assertEqual(Product.objects.values().get(pk=self.product.pk), before)

    def test_upload_never_publishes_private_product(self):
        for active in (True, False):
            Product.objects.filter(pk=self.product.pk).update(is_active=active, is_published=False)
            self.client.post(self.url, {"action":"upload_image", "upload-image":existing.image_upload(), "upload-sort_order":0})
            self.product.refresh_from_db()
            self.assertFalse(self.product.is_published)
            self.assertEqual(public_catalog_products(), [])

    def test_product_save_preserves_images_identity_history_and_business_tables(self):
        self.upload()
        unit = ProductSaleUnit.objects.create(product=self.product, name="Single", base_quantity=1)
        ProductPrice.objects.create(sale_unit=unit, amount=25, effective_start=timezone.now()-timedelta(days=1))
        models = [model for label in ("inventory", "production", "orders", "payments", "commitments")
                  for model in apps.get_app_config(label).get_models()]
        models += [ProductImage, ProductSaleUnit, ProductPrice]
        before = {model:list(model.objects.values()) for model in models}
        self.assertRedirects(self.client.post(self.url, self.values(sku="TAMPER", slug="tamper")), self.url)
        self.product.refresh_from_db()
        self.assertEqual(self.product.sku, "WTP-VEG-901")
        self.assertEqual(self.product.slug, "image-seedling")
        self.assertEqual(self.product.description, "Staff description")
        for model in models:
            self.assertEqual(list(model.objects.values()), before[model], model.__name__)

    def test_view_only_cannot_edit_or_change_any_image(self):
        record = self.upload()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        for action in ("save_product", "upload_image", "update_image", "delete_image", "save_sale_unit"):
            self.assertEqual(self.client.post(self.url, {"action":action,"image_id":record.pk}).status_code, 403)

    def test_sale_unit_edit_requires_existing_permission_and_preserves_price(self):
        unit = ProductSaleUnit.objects.create(product=self.product, name="Single", base_quantity=1)
        price = ProductPrice.objects.create(sale_unit=unit, amount=25, effective_start=timezone.now())
        before = ProductPrice.objects.values().get(pk=price.pk)
        values = {"action":"save_sale_unit", "sale_unit_id":unit.pk, f"unit-{unit.pk}-name":"Tray",
                  f"unit-{unit.pk}-base_quantity":"128", f"unit-{unit.pk}-is_active":"on"}
        self.assertEqual(self.client.post(self.url, values).status_code, 403)
        self.actor.user_permissions.add(Permission.objects.get(content_type__app_label="products", codename="change_productsaleunit"))
        self.assertRedirects(self.client.post(self.url, values), self.url)
        unit.refresh_from_db()
        self.assertEqual((unit.name, unit.base_quantity), ("Tray", 128))
        self.assertEqual(ProductPrice.objects.values().get(pk=price.pk), before)
        values[f"unit-{unit.pk}-base_quantity"] = "0"
        self.assertEqual(self.client.post(self.url, values).status_code, 200)
        unit.refresh_from_db()
        self.assertEqual(unit.base_quantity, 128)

    def test_edit_with_existing_stock_orders_payment_and_production_preserves_all_records(self):
        import uuid
        from decimal import Decimal
        from apps.dashboard.test_pos import POSLocationTests
        from apps.production.services import create_batch
        POSLocationTests.setUpTestData()
        fixture = POSLocationTests(methodName="test_bomet_default_and_location_specific_catalog")
        fixture.client = self.client
        self.client.force_login(fixture.actor)
        fixture.create()
        today = timezone.localdate()
        create_batch(batch_number="EDIT-SAFETY", product_id=fixture.product.pk,
                     start_date=today, expected_ready_date=today+timedelta(days=30),
                     quantity_started=Decimal("10"), notes="Isolated test", actor=fixture.actor,
                     correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(), location_id=fixture.bomet.pk)
        models = [model for label in ("inventory", "production", "orders", "payments", "commitments")
                  for model in apps.get_app_config(label).get_models()]
        models += [ProductPrice, ProductSaleUnit]
        before = {model: list(model.objects.values()) for model in models}
        url = reverse("dashboard:catalog_product_edit", args=[fixture.product.pk])
        self.assertRedirects(self.client.post(url, self.values()), url)
        response = self.client.post(url, self.values(base_inventory_unit="tray"))
        self.assertContains(response, "immutable after Inventory use")
        for model in models:
            self.assertEqual(list(model.objects.values()), before[model], model.__name__)
