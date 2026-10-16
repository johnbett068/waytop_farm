"""Opt-in Chrome verification using a test database and temporary media.

WAYTOP_IMAGE_BROWSER_TESTS=1 python manage.py test apps.products.test_image_browser
Requires Playwright and locally installed Chrome.
"""
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from unittest import skipUnless

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import clear_url_caches, reverse
from .test_images import image_upload


@skipUnless(os.environ.get("WAYTOP_IMAGE_BROWSER_TESTS") == "1", "Opt-in isolated Chrome image verification")
class ProductImageBrowserTests(StaticLiveServerTestCase):
    def test_upload_public_gallery_commerce_reorder_remove_and_placeholders(self):
        from playwright.sync_api import sync_playwright, expect
        from config import urls

        with tempfile.TemporaryDirectory(prefix="waytop-image-browser-") as media:
            module_name = "waytop_isolated_image_urls"
            module = ModuleType(module_name)
            sys.modules[module_name] = module
            try:
                with self.settings(MEDIA_ROOT=media, DEBUG=True, ROOT_URLCONF=module_name):
                    module.urlpatterns = static(settings.MEDIA_URL, document_root=media) + list(urls.urlpatterns)
                    clear_url_caches()
                    actor = get_user_model().objects.create_superuser(username="image-browser", password="test-only")
                    self.client.force_login(actor)
                    cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
                    public_path = reverse("products:product_detail", args=["browser-seedling"])
                    photos = {"First view": image_upload(color="green").read(), "Second view": image_upload(color="goldenrod").read()}
                    output = Path(settings.BASE_DIR) / ".tmp" / "product-image-verification"
                    output.mkdir(parents=True, exist_ok=True)
                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(channel="chrome", headless=True)
                        try:
                            context = browser.new_context(viewport={"width": 1440, "height": 1000})
                            context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": self.live_server_url}])
                            page = context.new_page()
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            page.goto(self.live_server_url + reverse("dashboard:dashboard"))
                            for name in ("No Image Seedling", "Browser Seedling"):
                                page.locator("[data-staff-navigation]").get_by_role("link", name="Products", exact=True).click()
                                page.get_by_role("link", name="+ Create Product", exact=True).click()
                                expect(page.locator("[data-first-product-image] legend")).to_have_text("Product image")
                                expect(page.locator('.catalog-image-guidance')).to_contain_text('960 × 768 px (5:4)')
                                expect(page.locator('.catalog-image-guidance')).to_contain_text('15728640 bytes')
                                expect(page.locator('.catalog-image-guidance')).to_contain_text('15 MiB')
                                page.locator('[name="name"]').fill(name)
                                page.locator('[name="category"]').select_option("VEG")
                                page.locator('[name="is_published"]').check()
                                page.locator('[name="price_amount"]').fill("25")
                                if name == "Browser Seedling":
                                    requests = []
                                    page.on("request", lambda request: requests.append(request.method))
                                    file_input = page.locator('[name="first-image-image"]')
                                    preview = page.locator("[data-image-preview]")
                                    for color in ("Second view", "First view"):
                                        file_input.set_input_files({"name": "farm.png", "mimeType": "image/png", "buffer": photos[color]})
                                        expect(preview).to_be_visible()
                                        page.wait_for_function("document.querySelector('[data-image-preview]').naturalWidth > 0")
                                        expect(page.locator('[data-image-details]')).to_contain_text('80 × 60 px')
                                        expect(page.locator('[data-image-details]')).to_contain_text('other dimensions are allowed')
                                        expect(page.locator('[data-image-details]')).to_contain_text('farm.png')
                                        if color == "Second view":
                                            file_input.set_input_files([])
                                            expect(preview).to_be_hidden()
                                            expect(page.locator('[data-image-details]')).to_be_hidden()
                                    self.assertNotIn("POST", requests)
                                    page.locator('[name="first-image-alt_text"]').fill("First view")
                                    page.screenshot(path=str(output / "create-image-preview.png"), full_page=True)
                                page.get_by_role("button", name="Save Product", exact=True).click()
                                expect(page.get_by_role("heading", name="Product Images", exact=True)).to_be_visible()
                                if name == "No Image Seedling":
                                    expect(page.locator(".catalog-image-card")).to_have_count(0)
                                else:
                                    expect(page.locator(".catalog-image-card")).to_have_count(1)
                                    expect(page.locator(".catalog-image-card img")).to_have_attribute("alt", "First view")
                                    expect(page.locator(".catalog-image-card h3")).to_have_text("Main image")
                            page.get_by_role("link", name="Edit Product", exact=True).click()
                            expect(page.get_by_role("heading", name="Edit Product", exact=True)).to_be_visible()
                            expect(page.get_by_text("How this Product is sold", exact=True)).to_be_visible()
                            page.locator('[name="description"]').fill("Browser verified description")
                            page.get_by_role("button", name="Save Changes", exact=True).click()
                            expect(page.locator('[name="description"]')).to_have_value("Browser verified description")
                            staff_path = page.url.removeprefix(self.live_server_url)
                            page.goto(self.live_server_url + public_path)
                            expect(page.locator(".product-gallery img")).to_have_attribute("alt", "First view")
                            page.goto(self.live_server_url + staff_path)
                            page.locator("[data-staff-navigation]").get_by_role("link", name="Products", exact=True).click()
                            expect(page).to_have_url(self.live_server_url + reverse("dashboard:catalog_products"))
                            page.screenshot(path=str(output / "product-list-edit.png"), full_page=True)
                            page.get_by_role("row").filter(has=page.get_by_role("link", name="Browser Seedling", exact=True)).get_by_role("link", name="Edit", exact=True).click()
                            expect(page).to_have_url(self.live_server_url + staff_path)
                            expect(page.get_by_role("heading", name="Product Images", exact=True)).to_be_visible()
                            page.get_by_role("link", name="Add Image", exact=True).click()
                            expect(page.locator(".catalog-image-upload").get_by_role("button", name="Upload image", exact=True)).to_be_visible()
                            page.locator(".catalog-image-card").get_by_label("Display order").fill("20")
                            page.locator(".catalog-image-card").get_by_role("button", name="Save image details").click()
                            for alt, order in (("Second view", "10"),):
                                form = page.locator(".catalog-image-upload")
                                form.locator('input[type="file"]').set_input_files({"name": "farm.png", "mimeType": "image/png", "buffer": photos[alt]})
                                expect(form.locator('[data-image-preview]')).to_be_visible()
                                expect(form.locator('[data-image-details]')).to_contain_text('80 × 60 px')
                                form.get_by_label("Alt text").fill(alt)
                                form.get_by_label("Display order").fill(order)
                                form.get_by_role("button", name="Upload image", exact=True).click()
                                expect(page.get_by_text("Product image uploaded.", exact=True)).to_be_visible()
                            expect(page.locator(".catalog-image-card")).to_have_count(2)
                            expect(page.locator(".catalog-image-card").first.locator("img")).to_have_attribute("alt", "Second view")
                            page.evaluate("window.scrollTo(0, 0)")
                            page.screenshot(path=str(output / "management.png"), full_page=True)
                            for path, selector in (("/", ".featured-products__media img"),
                                                   ("/products/", '.catalog-card[data-commerce-product="browser-seedling"] img'),
                                                   ("/products/search/?q=Browser", '.catalog-card[data-commerce-product="browser-seedling"] img')):
                                page.goto(self.live_server_url + path)
                                photograph = page.locator(selector).first
                                expect(photograph).to_have_attribute("alt", "Second view")
                                photograph.scroll_into_view_if_needed()
                                expect(photograph).to_be_visible()
                                page.wait_for_function("selector => { const img = document.querySelector(selector); return img && img.complete && img.naturalWidth > 0; }", arg=selector)
                            page.goto(self.live_server_url + public_path)
                            expect(page.locator(".product-gallery img")).to_have_attribute("alt", "Second view")
                            expect(page.locator(".product-gallery-additional img")).to_have_attribute("alt", "First view")
                            page.screenshot(path=str(output / "gallery-desktop.png"), full_page=True)
                            page.set_viewport_size({"width": 390, "height": 844})
                            page.screenshot(path=str(output / "gallery-mobile.png"), full_page=True)
                            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
                            page.set_viewport_size({"width": 1440, "height": 1000})
                            page.locator('[data-wishlist-toggle="browser-seedling"]').click()
                            page.locator("[data-cart-add]").click()
                            page.goto(self.live_server_url + "/cart/")
                            expect(page.locator(".cart-item__media img")).to_have_attribute("alt", "Second view")
                            page.locator("[data-cart-open]").first.click()
                            expect(page.locator(".mini-cart-item__media img")).to_have_attribute("alt", "Second view")
                            page.goto(self.live_server_url + "/wishlist/")
                            expect(page.locator(".wishlist-card__media img")).to_have_attribute("alt", "Second view")
                            page.goto(self.live_server_url + staff_path)
                            card = page.locator(".catalog-image-card").filter(has=page.locator('img[alt="First view"]'))
                            card.get_by_label("Display order").fill("5")
                            card.get_by_role("button", name="Save image details").click()
                            expect(page.locator(".catalog-image-card").first.locator("img")).to_have_attribute("alt", "First view")
                            page.goto(self.live_server_url + public_path)
                            expect(page.locator(".product-gallery img")).to_have_attribute("alt", "First view")
                            for next_alt in ("Second view", None):
                                page.goto(self.live_server_url + staff_path)
                                page.locator(".catalog-image-card").first.get_by_role("button", name="Remove image").click()
                                expect(page.get_by_text("Product images updated.", exact=True)).to_be_visible()
                                page.goto(self.live_server_url + public_path)
                                if next_alt:
                                    expect(page.locator(".product-gallery img")).to_have_attribute("alt", next_alt)
                                    expect(page.locator(".product-gallery-additional")).to_have_count(0)
                                else:
                                    expect(page.locator(".product-gallery .catalog-product-placeholder")).to_have_text("WT")
                            page.goto(self.live_server_url + "/products/")
                            expect(page.locator('.catalog-card[data-commerce-product="no-image-seedling"] .catalog-product-placeholder')).to_have_text("WT")
                            page.goto(self.live_server_url + staff_path)
                            page.locator('[name="is_published"]').uncheck()
                            page.get_by_role("button", name="Save Changes", exact=True).click()
                            form = page.locator(".catalog-image-upload")
                            form.locator('input[type="file"]').set_input_files({"name":"private.png", "mimeType":"image/png", "buffer":photos["First view"]})
                            form.get_by_role("button", name="Upload image", exact=True).click()
                            expect(page.locator('[name="is_published"]')).not_to_be_checked()
                            response = page.goto(self.live_server_url + public_path)
                            self.assertEqual(response.status, 404)
                            page.goto(self.live_server_url + staff_path)
                            page.set_viewport_size({"width":390,"height":844})
                            page.evaluate("window.scrollTo(0, 0)")
                            page.wait_for_timeout(400)  # Allow the navigation breakpoint transition to finish.
                            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),390)
                            page.screenshot(path=str(output / "edit-mobile.png"), full_page=True)
                            self.assertEqual(errors, [])
                        finally:
                            browser.close()
            finally:
                sys.modules.pop(module_name, None)
                clear_url_caches()
