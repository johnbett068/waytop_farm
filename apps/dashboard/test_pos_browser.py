"""Opt-in actual Chrome verification on Django's isolated test database.

WAYTOP_BROWSER_TESTS=1 python manage.py test apps.dashboard.test_pos_browser
Requires Playwright and locally installed Chrome; no production database writes.
"""
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from apps.inventory.models import InventoryMovement, Reservation
from apps.orders.models import Order
from apps.payments.models import Payment
from . import test_pos_bookings as fixtures


@skipUnless(os.environ.get("WAYTOP_BROWSER_TESTS") == "1", "Opt-in isolated Chrome verification")
class POSBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright
        fixtures.POSBookingTests.setUpTestData.__func__(fixtures.POSBookingTests)
        self.fixture = fixtures.POSBookingTests
        if self._testMethodName == "test_sales_workspace_above_fold_and_mobile":
            self.fixture.product.name = "Dany F1"
            self.fixture.product.save()
        self.client.force_login(self.fixture.actor)
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.browser = self.playwright.chromium.launch(channel="chrome", headless=True)
        self.addCleanup(self.browser.close)
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
        self.context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                                  "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                                  "url": self.live_server_url}])
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def database_counts(self):
        def read_counts():
            from django.db import close_old_connections
            close_old_connections()
            try:
                return (Order.objects.filter(status="CONFIRMED").count(),
                        Payment.objects.filter(state="CONFIRMED").count(),
                        InventoryMovement.objects.count(), Reservation.objects.count(), Order.objects.count())
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(read_counts).result()

    def open_pos(self):
        from django.urls import reverse
        self.page.goto(self.live_server_url + reverse("dashboard:pos"))

    def add_single(self):
        article = self.page.locator(".pos-products .pos-product").filter(has_text="Single seedling")
        article.get_by_role("button", name="Add to cart").click()

    def pay(self, method, reference=""):
        self.page.get_by_label("Payment method", exact=True).select_option(method)
        if method == "MPESA":
            self.page.get_by_label("M-Pesa Reference", exact=True).fill(reference)
        else:
            self.assertFalse(self.page.get_by_label("M-Pesa Reference", exact=True).is_visible())
        self.page.get_by_role("button", name="Confirm Payment" if "activity=bookings" in self.page.url else "Complete Sale", exact=True).click()

    def test_actual_cash_mpesa_sales_bookings_failure_branch_isolation_and_mobile(self):
        from playwright.sync_api import expect
        self.open_pos()
        expect(self.page.get_by_label("Location / Branch", exact=True)).to_have_value(str(self.fixture.bomet.pk))
        for mode in ("Sales", "Bookings"):
            self.page.get_by_role("navigation", name="POS activity").get_by_role("link", name=mode, exact=True).click()
            if mode == "Bookings":
                expect(self.page.locator(".pos-products")).to_contain_text("Expected readiness")
                expect(self.page.locator(".pos-products")).to_contain_text("3500 Single seedling available for booking at Bomet")
                self.page.get_by_label("Location / Branch", exact=True).select_option(str(self.fixture.other.pk))
                self.page.get_by_role("button", name="Switch location").click()
                expect(self.page.locator(".pos-products")).to_contain_text("1500 Single seedling available for booking at Other Branch")
                expect(self.page.locator(".pos-products")).not_to_contain_text("BOMET-PRODUCTION")
                self.page.get_by_label("Location / Branch", exact=True).select_option(str(self.fixture.bomet.pk))
                self.page.get_by_role("button", name="Switch location").click()
            for method in ("CASH", "MPESA"):
                self.add_single()
                self.pay(method, mode.upper()+"-BROWSER")
                expect(self.page.get_by_role("alert")).to_contain_text("Payment Confirmed" if mode == "Bookings" else "Sale completed successfully.")
                expect(self.page.get_by_text("Your cart is empty.", exact=True)).to_be_visible()
                expect(self.page.get_by_text("Verify payment", exact=True)).to_have_count(0)
        self.assertEqual(self.database_counts(), (4, 4, 4, 2, 4))
        self.add_single()
        self.pay("MPESA", "BOOKINGS-BROWSER")
        expect(self.page.get_by_role("alert")).to_contain_text("already confirmed")
        expect(self.page.get_by_text("Your cart is empty.", exact=True)).to_have_count(0)
        expect(self.page.get_by_role("button", name="Confirm Payment", exact=True)).to_be_enabled()
        self.assertEqual(self.database_counts(), (4, 4, 4, 2, 4))
        output = Path(settings.BASE_DIR) / ".tmp" / "pos-verification"
        output.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(output / "bookings-desktop.png"), full_page=True)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.wait_for_function("document.querySelector('.staff-sidebar').getBoundingClientRect().right <= 0")
        self.page.screenshot(path=str(output / "bookings-mobile.png"), full_page=True)
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)
        self.assertEqual(self.errors, [])

    def stock_balances(self):
        def read():
            from django.db import close_old_connections
            from apps.inventory.models import StockPosition
            close_old_connections()
            try:
                return dict(StockPosition.objects.values_list("location_id", "on_hand_base_quantity"))
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(read).result()

    def test_sales_payment_visibility_stock_failure_and_location_switch(self):
        from playwright.sync_api import expect
        self.open_pos()
        expect(self.page.locator(".pos-products")).to_contain_text("5 Single seedling available at Bomet")
        for method in ("CASH", "MPESA"):
            self.add_single()
            before = self.stock_balances()
            self.page.get_by_label("Payment method", exact=True).select_option(method)
            reference = self.page.get_by_label("M-Pesa Reference", exact=True)
            if method == "CASH":
                expect(reference).to_be_hidden()
                expect(reference).to_be_disabled()
                expect(self.page.locator("#pos-payment-help")).to_have_text("Confirm the cash payment to complete the sale.")
            else:
                expect(reference).to_be_visible()
                expect(reference).to_have_attribute("required", "")
                expect(self.page.locator("#pos-payment-help")).to_have_text("Enter the M-Pesa transaction reference to complete the sale.")
                expect(self.page.get_by_role("button", name="Complete Sale", exact=True)).to_be_disabled()
                expect(self.page.get_by_text("Your cart is empty.", exact=True)).to_have_count(0)
                self.assertEqual(self.stock_balances(), before)
            self.pay(method, "SALES-CLEANUP")
            expect(self.page.get_by_role("alert")).to_contain_text("Sale completed successfully.")
            expect(self.page.get_by_text("Your cart is empty.", exact=True)).to_be_visible()
            self.assertEqual(self.stock_balances()[self.fixture.bomet.pk], before[self.fixture.bomet.pk] - 1)
            self.assertEqual(self.stock_balances()[self.fixture.other.pk], before[self.fixture.other.pk])
            expect(self.page.get_by_role("button", name="Verify Payment", exact=True)).to_have_count(0)
        self.add_single()
        before = self.stock_balances()
        self.pay("MPESA", "SALES-CLEANUP")
        expect(self.page.get_by_role("alert")).to_contain_text("already confirmed")
        expect(self.page.get_by_text("Your cart is empty.", exact=True)).to_have_count(0)
        self.assertEqual(self.stock_balances(), before)
        self.page.get_by_label("Location / Branch", exact=True).select_option(str(self.fixture.other.pk))
        self.page.get_by_role("button", name="Switch location").click()
        expect(self.page.locator(".pos-products")).to_contain_text("20 Single seedling available at Other Branch")
        self.page.get_by_label("Payment method", exact=True).select_option("CASH")
        expect(self.page.get_by_role("button", name="Complete Sale", exact=True)).to_be_enabled()
        cart = self.page.locator(".pos-columns > section").nth(1)
        cart.get_by_label("Quantity", exact=True).fill("6")
        cart.get_by_role("button", name="Update", exact=True).click()
        self.page.get_by_label("Location / Branch", exact=True).select_option(str(self.fixture.bomet.pk))
        self.page.get_by_role("button", name="Switch location").click()
        expect(self.page.get_by_role("button", name="Complete Sale", exact=True)).to_be_disabled()
        self.assertEqual(self.stock_balances(), before)
        output = Path(settings.BASE_DIR) / ".tmp" / "pos-verification"
        output.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(output / "sales-cleanup-desktop.png"), full_page=True)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.wait_for_function("document.querySelector('.staff-sidebar').getBoundingClientRect().right <= 0")
        self.page.screenshot(path=str(output / "sales-cleanup-mobile.png"), full_page=True)
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)
        self.assertEqual(self.errors, [])

    def test_sales_workspace_above_fold_and_mobile(self):
        from playwright.sync_api import expect
        self.page.set_viewport_size({"width": 1366, "height": 768})
        self.open_pos()

        def above_fold():
            self.page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            for selector in ("h1", ".pos-tabs", "#pos-location", "#pos-search", ".pos-products .pos-product",
                             ".pos-products button", ".pos-checkout-panel h2", ".pos-total",
                             "#pos-customer", "#pos-payment-method", "[data-complete-sale]"):
                bounds = self.page.locator(selector).first.bounding_box()
                self.assertIsNotNone(bounds, selector)
                self.assertGreaterEqual(bounds["y"], 0, selector)
                self.assertLessEqual(bounds["y"] + bounds["height"], self.page.viewport_size["height"], selector)
            if self.page.locator("#pos-reference").is_visible():
                bounds = self.page.locator("#pos-reference").bounding_box()
                self.assertLessEqual(bounds["y"] + bounds["height"], self.page.viewport_size["height"])
            left = self.page.locator(".pos-catalog-panel").bounding_box()
            right = self.page.locator(".pos-checkout-panel").bounding_box()
            self.assertGreater(right["x"], left["x"] + left["width"])
            controls = self.page.locator('.pos-sales-controls').bounding_box()
            self.assertAlmostEqual(right["y"], controls["y"] - 16, delta=1, msg="Checkout must use space beside POS controls")

        above_fold()
        expect(self.page.locator("[data-complete-sale]")).to_be_disabled()
        expect(self.page.locator(".pos-products")).to_contain_text("Dany F1")
        expect(self.page.locator(".pos-product-image").first).to_be_visible()
        self.add_single()
        above_fold()
        expect(self.page.locator(".pos-total")).to_contain_text("12.55")
        expect(self.page.locator("[data-complete-sale]")).to_be_disabled()
        self.page.get_by_label("M-Pesa Reference", exact=True).fill("WORKSPACE-REF")
        expect(self.page.locator("[data-complete-sale]")).to_be_enabled()
        self.page.get_by_label("Payment method", exact=True).select_option("CASH")
        expect(self.page.locator("#pos-reference-field")).to_be_hidden()
        above_fold()
        output = Path(settings.BASE_DIR) / ".tmp" / "pos-verification"
        output.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(output / "workspace-desktop.png"), full_page=True)
        # Stress only the rendered list: no extra products, sales or inventory records.
        self.page.locator(".pos-cart-items").evaluate("""node => {
            for (let i = 0; i < 9; i++) {
                const row = node.querySelector('article').cloneNode(true);
                row.dataset.layoutFixture = 'true';
                row.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
                node.append(row);
            }
        }""")
        for width, height in ((1280, 600), (900, 768), (1024, 768), (1100, 768), (1366, 768), (1280, 720), (1440, 900)):
            self.page.set_viewport_size({"width": width, "height": height})
            for method in ("MPESA", "CASH"):
                self.page.locator("#pos-payment-method").select_option(method)
                self.page.wait_for_function("""() => {
                    const panel = document.querySelector('.pos-checkout-panel');
                    return panel.getBoundingClientRect().bottom <= innerHeight;
                }""")
                above_fold()
                self.assertTrue(self.page.locator(".pos-cart-items").evaluate("n => n.scrollHeight > n.clientHeight"))
                self.page.locator(".pos-cart-items").evaluate("n => n.scrollTop = n.scrollHeight")
                above_fold()
            self.page.screenshot(path=str(output / f"checkout-long-{width}x{height}.png"))
        self.page.locator('[data-layout-fixture]').evaluate_all("nodes => nodes.forEach(n => n.remove())")
        self.page.set_viewport_size({"width": 1366, "height": 768})
        # Exercise a long product area without creating extra business records.
        self.page.locator(".pos-catalog-panel").evaluate("node => node.style.minHeight = '1600px'")
        self.page.evaluate("window.scrollTo(0, 500)")
        bounds = self.page.locator("[data-complete-sale]").bounding_box()
        self.assertGreaterEqual(bounds["y"], 68)
        self.assertLessEqual(bounds["y"] + bounds["height"], 768)
        self.assertEqual(self.page.locator(".pos-checkout-panel").evaluate("node => getComputedStyle(node).position"), "sticky")
        self.page.locator(".pos-catalog-panel").evaluate("node => node.style.minHeight = ''")
        self.page.evaluate("window.scrollTo(0, 0)")
        before = self.stock_balances()
        self.page.get_by_role("button", name="Complete Sale", exact=True).click()
        expect(self.page.get_by_text("Your cart is empty.", exact=True)).to_be_visible()
        expect(self.page.get_by_role("alert")).to_contain_text("Sale completed successfully.")
        self.assertEqual(self.stock_balances()[self.fixture.bomet.pk], before[self.fixture.bomet.pk] - 1)
        above_fold()
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.wait_for_function("document.querySelector('.staff-sidebar').getBoundingClientRect().right <= 0")
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)
        left = self.page.locator(".pos-catalog-panel").bounding_box()
        right = self.page.locator(".pos-checkout-panel").bounding_box()
        self.assertGreater(right["y"], left["y"])
        self.page.locator("[data-complete-sale]").scroll_into_view_if_needed()
        expect(self.page.locator("[data-complete-sale]")).to_be_in_viewport()
        self.page.screenshot(path=str(output / "workspace-mobile.png"), full_page=True)
        self.assertEqual(self.errors, [])
