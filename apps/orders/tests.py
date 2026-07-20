from django.test import SimpleTestCase
from django.urls import reverse


class CheckoutPageTests(SimpleTestCase):
    def test_checkout_exposes_frontend_contract(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        for marker in (
            'data-checkout-page', 'data-checkout-stepper', 'data-checkout-form',
            'data-fulfillment="delivery"', 'data-fulfillment="pickup"',
            'data-payment="mpesa"', 'data-payment="cash_pickup"',
            'data-checkout-summary', 'data-checkout-empty', 'data-checkout-error',
            'data-checkout-permission',
        ):
            self.assertContains(response, marker)
        self.assertNotContains(response, "Select a branch")
        self.assertContains(response, "assigned after you place your request")

    def test_checkout_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "success"):
            response = self.client.get(reverse("orders:checkout") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')


class OrderConfirmationTests(SimpleTestCase):
    def test_confirmation_contains_complete_customer_projection(self):
        response = self.client.get(reverse("orders:success"))
        self.assertEqual(response.status_code, 200)
        for copy in (
            "Thank you, Jane Chebet", "WTF-260716-1042", "16 July 2026",
            "Home Delivery", "M-Pesa", "Payment Confirmed", "Anna F1 Tomato",
            "Hass Avocado", "KES 6,870", "Track Order", "Continue Shopping",
            "Download Receipt · Coming soon",
        ):
            self.assertContains(response, copy)
        self.assertContains(response, "no order, payment, receipt, notification, stock reservation or inventory movement")

    def test_confirmation_and_support_do_not_expose_operational_data_or_fake_email(self):
        response = self.client.get(reverse("orders:success"))
        for forbidden in ("Assigned Branch", "Assigned Staff", "Bomet Main Nursery", "Sotik Collection Point", "Kericho Collection Point", "support@"):
            self.assertNotContains(response, forbidden)
        self.assertContains(response, "Official email coming soon")
        self.assertContains(response, "+254 724 853 914")

    def test_confirmation_states_are_exercisable(self):
        for state in ("loading", "empty", "expired", "error", "permission", "success"):
            response = self.client.get(reverse("orders:success") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')
            self.assertContains(response, f"data-confirmation-{state}")


class OrderTrackingTests(SimpleTestCase):
    def test_guest_tracking_contract_and_details_render(self):
        response = self.client.get(reverse("orders:tracking") + "?state=success")
        self.assertEqual(response.status_code, 200)
        for marker in ("data-order-tracking", "data-tracking-form", "data-tracking-result", "data-tracking-not-found", "data-tracking-expired", "data-tracking-permission"):
            self.assertContains(response, marker)
        for copy in ("Order activity", "Order received", "Payment confirmed", "Preparing your seedlings", "Ready for dispatch", "Delivered", "Delivery information", "Customer notes"):
            self.assertContains(response, copy)

    def test_tracking_states_are_exercisable(self):
        for state in ("loading", "empty", "not-found", "expired", "error", "permission", "success"):
            response = self.client.get(reverse("orders:tracking") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')

    def test_tracking_response_excludes_operational_fields(self):
        response = self.client.get(reverse("orders:tracking") + "?state=success")
        for forbidden in ("Assigned Branch", "Assigned Staff", "Bomet Main Nursery", "Sotik Collection Point", "Kericho Collection Point", "internal_notes", "branch_id"):
            self.assertNotContains(response, forbidden)
