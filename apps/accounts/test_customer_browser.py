"""Opt-in Chrome journey, using Django's isolated test database."""
import os
from pathlib import Path
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from apps.inventory.models import InventoryLocation


@skipUnless(os.environ.get("WAYTOP_BROWSER_TESTS") == "1", "Opt-in Chrome verification")
class CustomerBrowserTests(StaticLiveServerTestCase):
    def test_registration_profile_login_mobile_and_staff(self):
        from playwright.sync_api import sync_playwright, expect
        InventoryLocation.objects.create(code="BOMET", name="Bomet")
        get_user_model().objects.create_superuser("stage1-staff", password="Nursery-Staff-728!")
        output=Path(settings.BASE_DIR)/".tmp"/"customer-stage1"
        output.mkdir(parents=True,exist_ok=True)
        pw=sync_playwright().start()
        self.addCleanup(pw.stop)
        browser=pw.chromium.launch(channel="chrome",headless=True)
        self.addCleanup(browser.close)
        page=browser.new_page(viewport={"width":1440,"height":900})
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.goto(self.live_server_url+"/")
        page.locator(".nav-bar__account").click()
        page.get_by_role("link",name="Create account",exact=True).filter(visible=True).click()
        page.get_by_label("Username",exact=False).fill("stage1-buyer")
        page.get_by_label("Full name",exact=False).fill("Stage One Buyer")
        page.get_by_label("Phone number",exact=False).fill("0724853914")
        page.locator("#id_password1").fill("Garden-Seedlings-728!")
        page.locator("#id_password2").fill("Garden-Seedlings-728!")
        page.get_by_role("button",name="Create account",exact=True).click()
        expect(page.get_by_role("heading",name="My Account",exact=True)).to_be_visible()
        expect(page.locator("#id_preferred_picking_location")).to_have_value("")
        page.get_by_label("County",exact=False).fill("Bomet")
        page.get_by_label("Town / Area",exact=False).fill("Sotik")
        page.get_by_label("Locality / landmark",exact=False).fill("Near the market")
        page.get_by_label("Preferred picking location",exact=False).select_option(label="Bomet")
        page.get_by_role("button",name="Save Changes",exact=True).click()
        expect(page.get_by_role("status").filter(has_text="saved")).to_be_visible()
        page.reload()
        expect(page.get_by_label("Town / Area",exact=False)).to_have_value("Sotik")
        expect(page.get_by_label("Preferred picking location",exact=False)).to_have_value("BOMET")
        expect(page.get_by_text("Your buyer details are complete.",exact=False)).to_be_visible()
        page.screenshot(path=str(output/"profile-desktop.png"),full_page=True)
        page.set_viewport_size({"width":390,"height":844})
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),390)
        page.screenshot(path=str(output/"profile-mobile.png"),full_page=True)
        response=page.goto(self.live_server_url+"/dashboard/")
        self.assertEqual(response.status,403)
        page.goto(self.live_server_url+"/accounts/my-account/")
        page.get_by_role("button",name="Sign out",exact=True).click()
        expect(page.get_by_role("heading",name="Customer sign in",exact=True)).to_be_visible()
        page.get_by_label("Username",exact=False).fill("stage1-buyer")
        page.get_by_label("Password",exact=False).fill("Garden-Seedlings-728!")
        page.get_by_role("button",name="Sign in",exact=True).click()
        expect(page.get_by_label("Town / Area",exact=False)).to_have_value("Sotik")
        page.get_by_role("button",name="Sign out",exact=True).click()
        page.goto(self.live_server_url+"/accounts/login/")
        page.get_by_label("Username",exact=False).fill("stage1-staff")
        page.get_by_label("Password",exact=False).fill("Nursery-Staff-728!")
        page.get_by_role("button",name="Sign in",exact=False).click()
        page.wait_for_url("**/dashboard/")
        self.assertEqual(page.request.get(self.live_server_url+"/dashboard/").status,200)
        self.assertEqual(errors,[])
        from concurrent.futures import ThreadPoolExecutor
        def saved_profile():
            from django.db import close_old_connections
            close_old_connections()
            try:
                user=get_user_model().objects.get(username="stage1-buyer")
                return user.is_staff, user.is_superuser, user.customer_profile.addresses.get().town_or_area
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(saved_profile).result(), (False, False, "Sotik"))
