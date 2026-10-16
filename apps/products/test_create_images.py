"""Optional first-image creation, using isolated database and media storage."""
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse

from .catalog import public_catalog_products
from .models import Product, ProductImage, ProductSaleUnit, ProductSkuSequence
from .test_images import image_upload


class ProductCreationImageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(username="create-with-image", is_staff=True)
        cls.actor.user_permissions.set(Permission.objects.filter(content_type__app_label="products", codename__in=(
            "view_product", "change_product", "add_product", "add_productsaleunit", "add_productprice")))

    def setUp(self):
        self.media = tempfile.TemporaryDirectory(prefix="waytop-create-image-")
        self.addCleanup(self.media.cleanup)
        override = self.settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.client.force_login(self.actor)
        self.url = reverse("dashboard:catalog_product_create")

    def values(self, **overrides):
        values = dict(name="New seedling", category="VEG", description="Entered description", base_inventory_unit="seedling",
                      is_active="on", is_published="on", sale_unit_name="Individual seedling", sale_unit_base_quantity="1")
        values.update(overrides)
        return values

    def test_without_image_preserves_optional_creation_and_placeholder(self):
        response = self.client.post(self.url, self.values())
        product = Product.objects.get()
        self.assertRedirects(response, reverse("dashboard:catalog_product_detail", args=[product.pk]))
        self.assertFalse(ProductImage.objects.exists())
        self.assertContains(self.client.get(reverse("products:product_detail", args=[product.slug])), ">WT</span>")

    def test_valid_first_image_alt_path_main_detail_and_public_catalog(self):
        response = self.client.post(self.url, self.values(**{"first-image-image": image_upload(), "first-image-alt_text": "  Seedling photo  "}))
        product = Product.objects.get()
        self.assertRedirects(response, reverse("dashboard:catalog_product_detail", args=[product.pk]))
        image = ProductImage.objects.get()
        self.assertEqual(image.product, product)
        self.assertEqual(image.image.name, f"products/{product.pk}/{image.pk.hex}.png")
        self.assertEqual((image.alt_text, image.sort_order), ("Seedling photo", 0))
        self.assertEqual(public_catalog_products()[0].catalog_main_image["url"], image.image.url)
        for url in (response.url, reverse("products:shop"), reverse("products:product_detail", args=[product.slug])):
            self.assertContains(self.client.get(url), image.image.url)

    def test_invalid_image_keeps_form_values_and_creates_no_catalog_records(self):
        response = self.client.post(self.url, self.values(**{"first-image-image": SimpleUploadedFile("fake.png", b"not an image")}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["image_form"].errors["image"])
        self.assertContains(response, "Entered description")
        self.assertContains(response, 'value="New seedling"')
        self.assertFalse(Product.objects.exists())
        self.assertFalse(ProductImage.objects.exists())
        self.assertFalse(ProductSaleUnit.objects.exists())

    def test_invalid_product_does_not_store_valid_image(self):
        response = self.client.post(self.url, self.values(name="", **{"first-image-image": image_upload()}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Product.objects.exists())
        self.assertEqual(list(Path(self.media.name).rglob("*.png")), [])

    def test_image_save_failure_rolls_back_product_sale_unit_sequence_and_file(self):
        before = list(ProductSkuSequence.objects.values_list("category", "last_value"))
        def fail(**kwargs):
            raise IntegrityError("simulated image persistence failure")
        post_save.connect(fail, sender=ProductImage, weak=False)
        try:
            with self.assertRaises(IntegrityError):
                self.client.post(self.url, self.values(**{"first-image-image": image_upload()}))
        finally:
            post_save.disconnect(fail, sender=ProductImage)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(ProductSaleUnit.objects.exists())
        self.assertFalse(ProductImage.objects.exists())
        self.assertEqual(list(ProductSkuSequence.objects.values_list("category", "last_value")), before)
        self.assertEqual(list(Path(self.media.name).rglob("*.png")), [])

    def test_storage_error_shows_error_and_preserves_input_without_partial_product(self):
        with patch("django.core.files.storage.filesystem.FileSystemStorage.save", side_effect=OSError("storage unavailable")):
            response = self.client.post(self.url, self.values(**{"first-image-image": image_upload()}))
        self.assertContains(response, "The image could not be stored")
        self.assertContains(response, 'value="New seedling"')
        self.assertFalse(Product.objects.exists())
        self.assertFalse(ProductImage.objects.exists())

    def test_existing_product_and_image_are_unchanged(self):
        self.client.post(self.url, self.values(**{"first-image-image": image_upload()}))
        original = Product.objects.get()
        image = ProductImage.objects.get()
        original_values = Product.objects.values().get(pk=original.pk)
        image_values = ProductImage.objects.values().get(pk=image.pk)
        contents = image.image.read()
        image.image.close()
        self.client.post(self.url, self.values(name="Another seedling", **{"first-image-image": image_upload(color="gold")}))
        self.assertEqual(Product.objects.values().get(pk=original.pk), original_values)
        self.assertEqual(ProductImage.objects.values().get(pk=image.pk), image_values)
        image.image.open()
        self.assertEqual(image.image.read(), contents)
        image.image.close()

    def test_image_does_not_automatically_publish_and_blank_alt_uses_product_name(self):
        self.client.post(self.url, self.values(is_published="", **{"first-image-image": image_upload()}))
        product = Product.objects.get()
        self.assertFalse(product.is_published)
        self.assertEqual(product.images.get().display_alt_text, product.name)
        self.assertEqual(public_catalog_products(), [])

    def test_existing_image_edit_permission_is_required_but_imageless_creation_is_allowed(self):
        self.actor.user_permissions.remove(Permission.objects.get(content_type__app_label="products", codename="change_product"))
        self.assertNotContains(self.client.get(self.url), 'type="file"')
        self.assertEqual(self.client.post(self.url, self.values(**{"first-image-image": image_upload()})).status_code, 403)
        self.assertFalse(Product.objects.exists())
        self.assertEqual(self.client.post(self.url, self.values()).status_code, 302)
