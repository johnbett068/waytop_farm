"""Catalog media regression tests: isolated database and temporary storage only."""
import importlib
from io import BytesIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from .catalog import commerce_catalog_projection, public_catalog_products
from .image_validation import MAX_IMAGE_BYTES
from .images import delete_product_image, update_product_image, upload_product_image
from .models import Product, ProductImage


def image_upload(name="photo.png", format="PNG", color="green"):
    stream = BytesIO()
    Image.new("RGB", (80, 60), color).save(stream, format=format)
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/" + format.lower())


class ProductImageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(username="image-editor", is_staff=True)
        cls.viewer = get_user_model().objects.create_user(username="image-viewer", is_staff=True)
        for codename in ("view_product", "change_product"):
            cls.actor.user_permissions.add(Permission.objects.get(content_type__app_label="products", codename=codename))
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label="products", codename="view_product"))
        cls.product = Product.objects.create(name="Image seedling", slug="image-seedling", sku="WTP-VEG-901",
                                             category="VEG", base_inventory_unit="seedling", is_published=True)

    def setUp(self):
        self.media = tempfile.TemporaryDirectory(prefix="waytop-image-tests-")
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.url = reverse("dashboard:catalog_product_detail", args=[self.product.pk])

    def upload(self, order=0, alt="", product=None, image=None):
        return upload_product_image(product_id=(product or self.product).pk, image=image or image_upload(),
                                    alt_text=alt, sort_order=order, actor=self.actor)

    def test_creation_relationship_storage_and_blank_alt_fallback(self):
        record = self.upload()
        self.assertEqual(record.product, self.product)
        self.assertEqual(record.image.name, f"products/{self.product.pk}/{record.pk.hex}.png")
        self.assertTrue(record.image.storage.exists(record.image.name))
        self.assertEqual(record.display_alt_text, self.product.name)
        self.assertEqual(record.display_url, record.image.url)
        self.assertFalse(Permission.objects.filter(content_type__app_label="products", content_type__model="productimage").exists())

    def test_supported_image_formats_are_verified_from_contents(self):
        for format, extension in (("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp"), ("GIF", "gif")):
            with self.subTest(format=format):
                self.upload(image=image_upload(f"farm.{extension}", format))
        self.assertEqual(ProductImage.objects.count(), 4)

    def test_invalid_spoofed_truncated_and_oversized_uploads_are_rejected(self):
        valid = image_upload()
        oversized = image_upload()
        oversized.size = MAX_IMAGE_BYTES + 1
        for uploaded in (SimpleUploadedFile("fake.png", b"not an image", content_type="image/png"),
                         image_upload("disguised.jpg"),
                         SimpleUploadedFile("truncated.png", valid.read()[:25]), oversized):
            with self.subTest(name=uploaded.name), self.assertRaises(ValidationError):
                self.upload(image=uploaded)
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertEqual(list(Path(self.media.name).rglob("*.png")), [])

    def test_deterministic_ties_and_first_image(self):
        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now):
            first, second = self.upload(order=3), self.upload(order=3)
        expected = sorted((first, second), key=lambda record: record.pk)
        self.assertEqual(list(self.product.images.all()), expected)
        projected = public_catalog_products()[0]
        self.assertEqual(projected.catalog_main_image["url"], expected[0].image.url)
        self.assertEqual([item["url"] for item in projected.catalog_images], [item.image.url for item in expected])

    def test_reordering_immediately_changes_main_and_alt_text(self):
        self.upload(order=1)
        second = self.upload(order=2)
        update_product_image(product_id=self.product.pk, image_id=second.pk, sort_order=0,
                             alt_text="  Farm seedling  ", actor=self.actor)
        projected = public_catalog_products()[0]
        self.assertEqual(projected.catalog_main_image, {"url": second.image.url, "alt": "Farm seedling"})

    def test_deleting_main_promotes_next_and_only_removes_its_file_after_commit(self):
        first, second = self.upload(order=1), self.upload(order=2)
        with self.captureOnCommitCallbacks(execute=True):
            delete_product_image(product_id=self.product.pk, image_id=first.pk, actor=self.actor)
            self.assertTrue(first.image.storage.exists(first.image.name))
        self.assertFalse(first.image.storage.exists(first.image.name))
        self.assertTrue(second.image.storage.exists(second.image.name))
        self.assertEqual(public_catalog_products()[0].catalog_main_image["url"], second.image.url)

    def test_rolled_back_deletion_preserves_record_and_file(self):
        record = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                delete_product_image(product_id=self.product.pk, image_id=record.pk, actor=self.actor)
                raise RuntimeError("rollback")
        self.assertTrue(ProductImage.objects.filter(pk=record.pk).exists())
        self.assertTrue(record.image.storage.exists(record.image.name))

    def test_failed_database_save_cleans_up_uploaded_file(self):
        def fail_save(**kwargs):
            raise IntegrityError("simulated persistence failure")
        post_save.connect(fail_save, sender=ProductImage, weak=False)
        try:
            with self.assertRaises(IntegrityError):
                self.upload()
        finally:
            post_save.disconnect(fail_save, sender=ProductImage)
        self.assertFalse(ProductImage.objects.exists())
        self.assertEqual(list(Path(self.media.name).rglob("*.png")), [])

    def test_cannot_attach_existing_path_or_move_image_to_another_product(self):
        record = self.upload()
        with self.assertRaises(ValidationError):
            ProductImage.objects.create(product=self.product, image=record.image.name)
        other = Product.objects.create(name="Other", slug="other", sku="WTP-VEG-902", category="VEG", base_inventory_unit="seedling")
        record.product = other
        with self.assertRaises(ValidationError):
            record.save()
        record.refresh_from_db()
        self.assertEqual(record.product_id, self.product.pk)

    def test_public_cards_home_search_and_detail_use_ordered_images(self):
        second = self.upload(order=20, alt="Second seedling view")
        first = self.upload(order=10, alt="Main seedling view")
        for url in ("/", reverse("products:shop"), reverse("products:search") + "?q=Image"):
            response = self.client.get(url)
            self.assertContains(response, first.image.url)
            self.assertContains(response, 'alt="Main seedling view"')
            self.assertNotContains(response, second.image.url)
        response = self.client.get(reverse("products:product_detail", args=[self.product.slug]))
        self.assertContains(response, second.image.url)
        html = response.content.decode()
        self.assertLess(html.index(first.image.url), html.index(second.image.url))

    def test_no_image_and_missing_file_use_placeholder_without_broken_urls(self):
        for url in ("/", reverse("products:shop"), reverse("products:product_detail", args=[self.product.slug])):
            self.assertContains(self.client.get(url), ">WT<")
        record = self.upload()
        record.image.storage.delete(record.image.name)
        response = self.client.get(reverse("products:product_detail", args=[self.product.slug]))
        self.assertContains(response, ">WT</span>")
        self.assertNotContains(response, record.image.url)
        self.assertIsNone(commerce_catalog_projection(public_catalog_products())[0]["main_image"])

    def test_unpublished_and_inactive_products_with_images_stay_private(self):
        for active, sku in ((True, "WTP-VEG-903"), (False, "WTP-VEG-904")):
            product = Product.objects.create(name="Private seedling", slug=sku.lower(), sku=sku, category="VEG",
                                             base_inventory_unit="seedling", is_active=active, is_published=False)
            record = self.upload(product=product)
            self.assertNotIn(product.pk, [item.pk for item in public_catalog_products()])
            for url in ("/", reverse("products:shop"), reverse("products:search") + "?q=Private", "/cart/", "/wishlist/"):
                self.assertNotContains(self.client.get(url), record.image.url)
            self.assertEqual(self.client.get(reverse("products:product_detail", args=[product.slug])).status_code, 404)

    def test_commerce_projection_adds_only_main_thumbnail_and_preserves_identity_contract(self):
        main, second = self.upload(order=0), self.upload(order=1)
        payload = commerce_catalog_projection(public_catalog_products())[0]
        self.assertEqual(set(payload), {"slug", "name", "description", "product_url", "sale_units", "main_image"})
        self.assertEqual(payload["main_image"], {"url": main.image.url, "alt": self.product.name})
        self.assertNotIn(second.image.url, str(payload))

    def test_images_are_prefetched_without_per_product_database_queries(self):
        self.upload()
        with self.assertNumQueries(3):  # Products, empty sale units, images; no prices when no units exist.
            products = public_catalog_products()
            commerce_catalog_projection(products)

    def test_staff_upload_edit_delete_and_preview(self):
        self.client.force_login(self.actor)
        response = self.client.post(self.url, {"action": "upload_image", "upload-image": image_upload(),
                                              "upload-alt_text": "Farm photograph", "upload-sort_order": 12})
        self.assertRedirects(response, self.url)
        record = self.product.images.get()
        self.assertContains(self.client.get(self.url), record.image.url)
        response = self.client.post(self.url, {"action": "update_image", "image_id": record.pk,
                                              f"image-{record.pk}-alt_text": "Updated photograph",
                                              f"image-{record.pk}-sort_order": 2})
        self.assertRedirects(response, self.url)
        record.refresh_from_db()
        self.assertEqual((record.alt_text, record.sort_order), ("Updated photograph", 2))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(self.url, {"action": "delete_image", "image_id": record.pk}), self.url)
        self.assertFalse(record.image.storage.exists(record.image.name))

    def test_viewer_cannot_upload_update_or_delete_via_view_or_service(self):
        record = self.upload()
        self.client.force_login(self.viewer)
        self.assertContains(self.client.get(self.url), record.image.url)
        self.assertNotContains(self.client.get(self.url), "catalog-image-upload")
        self.assertContains(self.client.get(self.url), "You have read-only access to Product images.")
        for action in ("upload_image", "update_image", "delete_image"):
            self.assertEqual(self.client.post(self.url, {"action": action, "image_id": record.pk}).status_code, 403)
        for command, values in ((upload_product_image, {"image": image_upload(), "alt_text": "", "sort_order": 0}),
                                (update_product_image, {"image_id": record.pk, "alt_text": "", "sort_order": 0}),
                                (delete_product_image, {"image_id": record.pk})):
            with self.assertRaises(PermissionDenied):
                command(product_id=self.product.pk, actor=self.viewer, **values)
        self.assertTrue(ProductImage.objects.filter(pk=record.pk).exists())

    def test_anonymous_nonstaff_and_inactive_users_cannot_change_images(self):
        self.assertEqual(self.client.post(self.url, {"action": "upload_image"}).status_code, 302)
        for active, staff in ((True, False), (False, True)):
            actor = get_user_model().objects.create_user(username=f"denied-{active}", is_active=active, is_staff=staff)
            actor.user_permissions.set(self.actor.user_permissions.all())
            self.client.force_login(actor)
            self.assertIn(self.client.post(self.url, {"action": "upload_image"}).status_code, (302, 403))
            with self.assertRaises(PermissionDenied):
                upload_product_image(product_id=self.product.pk, actor=actor, image=image_upload(), alt_text="", sort_order=0)

    def test_wrong_product_image_cannot_be_deleted_or_reordered(self):
        other = Product.objects.create(name="Other", slug="other", sku="WTP-VEG-905", category="VEG", base_inventory_unit="seedling")
        record = self.upload(product=other)
        self.client.force_login(self.actor)
        for action in ("update_image", "delete_image"):
            self.assertEqual(self.client.post(self.url, {"action": action, "image_id": record.pk}).status_code, 404)
        self.assertTrue(record.image.storage.exists(record.image.name))

    def test_invalid_upload_and_order_errors_render_without_creating_records(self):
        self.client.force_login(self.actor)
        response = self.client.post(self.url, {"action": "upload_image", "upload-image": SimpleUploadedFile("fake.png", b"fake"),
                                              "upload-alt_text": "", "upload-sort_order": 0})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["upload_form"].errors)
        self.assertFalse(ProductImage.objects.exists())
        record = self.upload()
        response = self.client.post(self.url, {"action": "update_image", "image_id": record.pk,
                                              f"image-{record.pk}-alt_text": "", f"image-{record.pk}-sort_order": -1})
        self.assertContains(response, "Review the image details")
        record.refresh_from_db()
        self.assertEqual(record.sort_order, 0)

    def test_development_media_routes_are_debug_only(self):
        from config import urls
        record = self.upload()
        try:
            for debug, status in ((True, 200), (False, 404)):
                with override_settings(DEBUG=debug):
                    importlib.reload(urls)
                    clear_url_caches()
                    response = self.client.get(record.image.url)
                    self.assertEqual(response.status_code, status)
                    response.close()
        finally:
            importlib.reload(urls)
            clear_url_caches()
