from django.test import TestCase
from django.urls import reverse


class WishlistPageTests(TestCase):
    def test_wishlist_page_exposes_frontend_state_contract(self):
        response = self.client.get(reverse("wishlist:wishlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-commerce-page="wishlist"')
        self.assertContains(response, "data-wishlist-grid")
        self.assertContains(response, "data-wishlist-empty")
        self.assertContains(response, "data-commerce-loading")
        self.assertContains(response, "data-commerce-error")

    def test_global_shell_exposes_shared_catalog_and_mini_cart(self):
        response = self.client.get(reverse("wishlist:wishlist"))
        self.assertContains(response, 'id="commerce-catalog-data"')
        self.assertContains(response, 'id="mini-cart"')
        self.assertContains(response, "data-cart-count")
        self.assertContains(response, "data-wishlist-count")
