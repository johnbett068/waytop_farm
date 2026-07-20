from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class HomePageTests(SimpleTestCase):
    def test_homepage_renders_final_shell_and_mock_catalog_contract(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/home.html")
        self.assertEqual(len(response.context["categories"]), 4)
        self.assertEqual(len(response.context["featured_products"]), 4)
        self.assertContains(response, "Anna F1 Tomato")
        self.assertContains(response, "Skip to main content")

    def test_homepage_does_not_advertise_unbuilt_routes(self):
        response = self.client.get(reverse("core:home"))

        for broken_path in ("/shop/", "/categories/", "/search/", "/account/"):
            self.assertNotContains(response, f'href="{broken_path}"')

    def test_homepage_uses_editorial_hero_and_evidence_safe_copy(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "Healthy seedlings.")
        self.assertContains(response, "WayTop Farm &amp; Nurseries")
        self.assertContains(response, "Growing with care in Bomet")
        self.assertContains(response, "Based in Bomet")
        self.assertContains(response, "Practical guidance")
        self.assertContains(response, 'class="home-edge-art"')
        self.assertContains(response, 'class="home-edge-art__side home-edge-art__side--left"')
        self.assertContains(response, 'class="home-edge-art__side home-edge-art__side--right"')
        self.assertContains(response, "images/home/hero-editorial-720.webp")
        self.assertContains(response, "images/home/categories/vegetable-seedlings-480.webp")
        self.assertContains(response, 'loading="lazy"')
        self.assertNotContains(response, "Real varieties. Ready to explore.")
        self.assertNotContains(response, "certified vegetable")
        self.assertNotContains(response, "5,000+")
        self.assertNotContains(response, "Verified Customer")

    def test_primary_navigation_marks_only_the_current_page_active(self):
        home_response = self.client.get(reverse("core:home"))
        shop_response = self.client.get(reverse("products:shop"))

        self.assertContains(
            home_response,
            'href="/" class="nav-bar__link" aria-current="page">Home',
        )
        self.assertNotContains(
            shop_response,
            'href="/" class="nav-bar__link" aria-current="page">Home',
        )
        self.assertContains(
            shop_response,
            'class="nav-bar__link" aria-current="page">Shop',
        )

    def test_business_phone_is_centralized_and_formatted_for_templates(self):
        response = self.client.get(reverse("core:home"))
        legacy_phone = "".join(("+254", "700", "000", "000"))

        self.assertContains(response, "tel:+254724853914")
        self.assertContains(response, "+254 724 853 914")
        self.assertNotContains(response, legacy_phone)

    @override_settings(DEBUG=False)
    def test_not_found_uses_branded_error_page(self):
        response = self.client.get("/not-a-real-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "We could not find that page", status_code=404)
