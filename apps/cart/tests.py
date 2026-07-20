from django.test import SimpleTestCase
from django.urls import reverse


class CartPageTests(SimpleTestCase):
    def test_cart_page_exposes_frontend_state_and_summary_contract(self):
        response = self.client.get(reverse("cart:cart"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-commerce-page="cart"')
        self.assertContains(response, "data-cart-items")
        self.assertContains(response, "data-cart-empty")
        self.assertContains(response, "data-commerce-loading")
        self.assertContains(response, "data-commerce-error")
        self.assertContains(response, "Proceed to checkout")
        self.assertContains(response, "No payment, order creation or stock reservation occurs")
        self.assertNotContains(response, "Preferred branch")

    def test_cart_error_state_can_be_exercised(self):
        response = self.client.get(reverse("cart:cart") + "?state=error")
        self.assertContains(response, 'data-state-mode="error"')
