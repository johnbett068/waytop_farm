import tempfile

from django.test import TestCase
from django.urls import reverse

from apps.dashboard import test_pos as fixtures
from apps.products.images import upload_product_image
from apps.products.test_images import image_upload


class POSWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.POSLocationTests.setUpTestData.__func__(cls)

    def test_existing_main_image_and_missing_file_placeholder(self):
        self.client.force_login(self.actor)
        url = reverse("dashboard:pos")
        self.assertContains(self.client.get(url), 'aria-label="No product image"')
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            photo = upload_product_image(product_id=self.product.pk, image=image_upload(),
                                         alt_text="Tomato seedlings", sort_order=0, actor=self.actor)
            response = self.client.get(url)
            self.assertContains(response, photo.display_url)
            self.assertContains(response, 'alt="Tomato seedlings"')
            self.assertNotContains(response, 'aria-label="No product image"')
            photo.image.storage.delete(photo.image.name)
            self.assertContains(self.client.get(url), 'aria-label="No product image"')
