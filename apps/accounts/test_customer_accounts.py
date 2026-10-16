from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.customers.models import Customer, CustomerAddress
from apps.customers.accounts import register_customer, missing_profile_fields, save_customer_profile
from apps.inventory.models import InventoryLocation
from .customer_forms import CustomerRegistrationForm, CustomerProfileForm

User = get_user_model()


class CustomerAccountTests(TestCase):
    password = "Garden-Seedlings-728!"

    @classmethod
    def setUpTestData(cls):
        cls.bomet = InventoryLocation.objects.create(code="BOMET", name="Bomet")
        cls.inactive = InventoryLocation.objects.create(code="CLOSED", name="Closed", is_active=False)
        cls.restricted = InventoryLocation.objects.create(code="RESTRICTED", name="Restricted", allows_saleable_stock=False)

    def registration(self, username="buyer"):
        return dict(username=username, full_name="Test Buyer", phone="0724853914", email="",
                    password1=self.password, password2=self.password)

    def make_customer(self, username="buyer"):
        form = CustomerRegistrationForm(self.registration(username))
        self.assertTrue(form.is_valid(), form.errors)
        return register_customer(form)

    def profile_data(self, **changes):
        data = dict(full_name="Updated Buyer", phone="0712345678", email="",
                    county="Bomet", town_or_area="Sotik", address_line="Near the market",
                    preferred_picking_location=self.bomet.code)
        data.update(changes)
        return data

    def test_registration_atomic_normal_user_and_no_default_location(self):
        response = self.client.post(reverse("accounts:customer_register"), {
            **self.registration(), "is_staff": "true", "is_superuser": "true"})
        self.assertRedirects(response, reverse("accounts:customer_profile"))
        user = User.objects.get(username="buyer")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertEqual(user.customer_profile.display_name, "Test Buyer")
        self.assertEqual(user.customer_profile.phone, "+254724853914")
        self.assertIsNone(user.customer_profile.preferred_picking_location_id)
        self.assertFalse(user.customer_profile.addresses.exists())
        self.assertEqual(missing_profile_fields(user), ["Your location", "Preferred picking location"])

    def test_registration_failure_rolls_back_user(self):
        form = CustomerRegistrationForm(self.registration())
        self.assertTrue(form.is_valid(), form.errors)
        with patch("apps.customers.accounts.Customer.objects.create", side_effect=ValidationError("failure")):
            with self.assertRaises(ValidationError):
                register_customer(form)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)

    def test_registration_invalid_and_duplicate_credentials(self):
        for changes in ({"phone":"bad"}, {"full_name":" "}, {"password2":"wrong"}, {"email":"bad"}):
            self.client.post(reverse("accounts:customer_register"), {**self.registration(), **changes})
            self.assertEqual(User.objects.count(), 0)
        self.make_customer()
        response = self.client.post(reverse("accounts:customer_register"), self.registration())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Customer.objects.count(), 1)

    def test_no_automatic_matching_of_existing_customer(self):
        old = Customer.objects.create(display_name="Test Buyer", phone="0724853914")
        before = Customer.objects.filter(pk=old.pk).values().get()
        user = self.make_customer()
        self.assertNotEqual(user.customer_profile.pk, old.pk)
        self.assertEqual(Customer.objects.filter(pk=old.pk).values().get(), before)
        with self.assertRaises(ValidationError):
            Customer.objects.create(owner=user, display_name="Duplicate")

    def test_customer_login_logout_and_staff_separation(self):
        user = self.make_customer()
        response = self.client.post(reverse("accounts:customer_login"), {
            "username":user.username,"password":self.password,"next":"https://example.com"})
        self.assertRedirects(response, reverse("accounts:customer_profile"))
        for url in ("/dashboard/", "/dashboard/pos/", "/accounts/profile/"):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:customer_logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:customer_logout")), reverse("accounts:customer_login"))
        response = self.client.post(reverse("accounts:login"), {"username":user.username,"password":self.password})
        self.assertIn("Invalid staff credentials.", response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_access_unchanged(self):
        user = User.objects.create_superuser("staff", password=self.password)
        response = self.client.post(reverse("accounts:login"), {"username":user.username,"password":self.password})
        self.assertRedirects(response, reverse("dashboard:dashboard"))
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:customer_profile")).status_code, 403)
        self.client.logout()
        response = self.client.post(reverse("accounts:customer_login"), {"username":user.username,"password":self.password})
        self.assertContains(response, "Use a customer account")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unowned_and_inactive_profiles_are_not_created_or_accessible(self):
        user = User.objects.create_user("unowned", password=self.password)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:customer_profile")).status_code, 403)
        self.assertFalse(Customer.objects.exists())
        user = self.make_customer()
        customer=user.customer_profile
        customer.is_active=False
        customer.save()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:customer_profile")).status_code, 403)
        self.client.logout()
        self.client.post(reverse("accounts:customer_login"), {"username":user.username,"password":self.password})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_persistence_completeness_and_optional_email(self):
        user = self.make_customer()
        self.client.force_login(user)
        url = reverse("accounts:customer_profile")
        for email in ("Buyer@Example.com", ""):
            self.assertRedirects(self.client.post(url, self.profile_data(email=email)), url)
            customer=Customer.objects.get(owner=user)
            self.assertEqual(customer.display_name,"Updated Buyer")
            self.assertEqual(customer.phone,"+254712345678")
            self.assertEqual(customer.email,email.lower())
            self.assertEqual(customer.preferred_picking_location,self.bomet)
            address=customer.addresses.get()
            self.assertEqual((address.county,address.town_or_area,address.address_line),("Bomet","Sotik","Near the market"))
            self.assertEqual(missing_profile_fields(user), [])
            self.assertContains(self.client.get(url), "Sotik")
        self.bomet.is_active=False
        self.bomet.save()
        self.assertEqual(missing_profile_fields(user), ["Preferred picking location"])

    def test_profile_validation_and_no_default(self):
        user=self.make_customer()
        self.client.force_login(user)
        url=reverse("accounts:customer_profile")
        response=self.client.get(url)
        self.assertContains(response, 'value="" selected')
        for field,value in (("preferred_picking_location", ""), ("preferred_picking_location", "unknown"),
                            ("preferred_picking_location", self.inactive.code), ("preferred_picking_location", self.restricted.code),
                            ("phone","bad"),("full_name",""),("county",""),("town_or_area",""),("address_line","")):
            response=self.client.post(url,self.profile_data(**{field:value}))
            self.assertEqual(response.status_code,200)
            self.assertIn(field,response.context["form"].errors)
            self.assertFalse(CustomerAddress.objects.exists())
            self.assertIsNone(Customer.objects.get(owner=user).preferred_picking_location_id)

    def test_location_revalidated_at_write_and_atomic_profile_save(self):
        user=self.make_customer()
        form=CustomerProfileForm(self.profile_data())
        self.assertTrue(form.is_valid(),form.errors)
        self.bomet.is_active=False
        self.bomet.save()
        with self.assertRaises(ValidationError):
            save_customer_profile(user=user,data=form.cleaned_data)
        self.bomet.is_active=True
        self.bomet.save()
        with patch("apps.customers.accounts.CustomerAddress.save",side_effect=ValidationError("failure")):
            with self.assertRaises(ValidationError):
                save_customer_profile(user=user,data=form.cleaned_data)
        self.assertEqual(Customer.objects.get(owner=user).display_name,"Test Buyer")

    def test_ownership_ignores_submitted_customer_user_and_address_ids(self):
        a=self.make_customer("buyer-a"); b=self.make_customer("buyer-b")
        other=b.customer_profile
        address=CustomerAddress.objects.create(customer=other,county="Other",town_or_area="Private",address_line="Private landmark",is_default=True)
        before=Customer.objects.filter(pk=other.pk).values().get()
        self.client.force_login(a)
        url=reverse("accounts:customer_profile")
        self.client.post(url,self.profile_data(customer_id=str(other.pk),owner=str(b.pk),address_id=str(address.pk)))
        self.assertEqual(Customer.objects.filter(pk=other.pk).values().get(),before)
        address.refresh_from_db()
        self.assertEqual(address.town_or_area,"Private")
        self.assertNotContains(self.client.get(url+"?customer_id="+str(other.pk)),"Private landmark")
        self.assertEqual(self.client.get(url+str(other.pk)+"/").status_code,404)

    def test_empty_location_configuration_and_csrf(self):
        InventoryLocation.objects.update(is_active=False)
        user=self.make_customer();self.client.force_login(user)
        self.assertContains(self.client.get(reverse("accounts:customer_profile")),"No picking locations are currently available")
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(user)
        self.assertEqual(csrf.post(reverse("accounts:customer_profile"),self.profile_data()).status_code,403)
        self.assertEqual(csrf.post(reverse("accounts:customer_register"),self.registration()).status_code,403)

    def test_checkout_remains_unimplemented(self):
        user=self.make_customer();self.client.force_login(user)
        self.assertContains(self.client.get("/orders/checkout/"),"Checkout is not available yet")

    def test_database_rejects_second_profile_for_same_owner(self):
        user = self.make_customer()
        unowned = Customer.objects.create(display_name="Legacy customer")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.filter(pk=unowned.pk).update(owner=user)
        unowned.refresh_from_db()
        self.assertIsNone(unowned.owner_id)
