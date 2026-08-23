import uuid

from django.contrib import admin
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse


User = get_user_model()


class UserModelTests(TestCase):
    def test_user_has_stable_uuid_identity_and_timestamps(self):
        user = User.objects.create_user(username="operator", password="strong-test-password")
        original_id = user.pk
        self.assertIsInstance(original_id, uuid.UUID)
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)
        user.first_name = "Updated"
        user.save()
        self.assertEqual(user.pk, original_id)

    def test_password_is_hashed_and_can_be_changed_securely(self):
        raw_password = "strong-test-password"
        user = User.objects.create_user(username="operator", password=raw_password)
        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))
        user.set_password("different-strong-password")
        user.save()
        self.assertTrue(user.check_password("different-strong-password"))
        self.assertFalse(user.check_password(raw_password))

    def test_activation_and_deactivation(self):
        user = User.objects.create_user(username="operator", password="strong-test-password")
        self.assertTrue(user.is_active)
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        self.assertFalse(User.objects.get(pk=user.pk).is_active)


class AuthenticationTests(TestCase):
    password = "strong-test-password"

    def setUp(self):
        self.user = User.objects.create_user(
            username="staff-user", password=self.password, is_staff=True
        )

    def test_valid_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": self.password},
        )
        self.assertRedirects(response, reverse("dashboard:dashboard"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_login_page_is_a_staff_only_post_form_with_csrf(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WayTop Farm Operations")
        self.assertContains(response, "Sign in to your account")
        self.assertContains(response, "Staff access only")
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'images/logo/logo.svg')
        self.assertNotContains(response, "Create account")
        self.assertNotContains(response, 'id="mini-cart"')
        self.assertNotContains(response, 'class="nav-bar"')

    def test_login_fields_are_labelled_and_have_safe_browser_attributes(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, 'type="text" name="username"')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'for="id_password"')
        self.assertContains(response, 'type="password" name="password"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, "Skip to sign in")

    def test_login_rejects_post_without_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": self.password},
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, f'value="{self.user.username}"')
        self.assertNotContains(response, "username does not exist")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_required_field_errors_are_visible_and_accessible(self):
        response = self.client.post(reverse("accounts:login"), {"username": "", "password": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.", count=2)
        self.assertContains(response, 'aria-invalid="true"', count=2)

    def test_inactive_user_cannot_authenticate_or_access_staff(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active", "updated_at"])
        self.assertIsNone(authenticate(username=self.user.username, password=self.password))
        self.assertFalse(self.client.login(username=self.user.username, password=self.password))
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('dashboard:dashboard')}",
        )

    def test_active_nonstaff_user_cannot_use_staff_login_or_profile(self):
        nonstaff = User.objects.create_user(
            username="nonstaff-user", password=self.password, is_staff=False
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"username": nonstaff.username, "password": self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")
        self.assertNotIn("_auth_user_id", self.client.session)

        self.client.force_login(nonstaff)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 403)

    def test_logout_remains_post_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("accounts:login"))


class AuthorizationTests(TestCase):
    def test_unauthenticated_user_cannot_access_staff_routes(self):
        for route in ("dashboard:dashboard", "dashboard:orders", "dashboard:production", "dashboard:inventory", "dashboard:pos"):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_authenticated_staff_user_can_access_staff_routes(self):
        user = User.objects.create_user(
            username="staff-user", password="strong-test-password", is_staff=True
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard:dashboard")).status_code, 200)

    def test_authenticated_nonstaff_user_cannot_access_staff_routes(self):
        user = User.objects.create_user(username="ordinary-user", password="strong-test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_group_permission_is_inherited_through_django_auth(self):
        user = User.objects.create_user(username="inventory-user", password="strong-test-password")
        group = Group.objects.create(name="Inventory test group")
        permission = Permission.objects.get(
            content_type__app_label="accounts", codename="view_user"
        )
        group.permissions.add(permission)
        user.groups.add(group)
        self.assertTrue(user.has_perm("accounts.view_user"))


class UserAdminTests(TestCase):
    def test_custom_user_uses_django_user_admin(self):
        registered_admin = admin.site._registry[User]
        self.assertIsInstance(registered_admin, UserAdmin)
        self.assertIn("created_at", registered_admin.readonly_fields)
        self.assertIn("updated_at", registered_admin.readonly_fields)

    def test_superuser_can_open_admin_and_create_user_with_hashed_password(self):
        superuser = User.objects.create_superuser(
            username="owner", password="strong-owner-password", email="owner@example.com"
        )
        self.client.force_login(superuser)
        add_url = reverse("admin:accounts_user_add")
        self.assertEqual(self.client.get(add_url).status_code, 200)
        response = self.client.post(
            add_url,
            {
                "username": "created-in-admin",
                "password1": "admin-created-strong-password",
                "password2": "admin-created-strong-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username="created-in-admin")
        self.assertTrue(created.check_password("admin-created-strong-password"))
        self.assertFalse(created.is_staff)

    def test_superuser_flags_and_deactivation_use_standard_fields(self):
        superuser = User.objects.create_superuser(
            username="owner", password="strong-owner-password"
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        superuser.is_active = False
        superuser.save(update_fields=["is_active", "updated_at"])
        self.assertFalse(User.objects.get(pk=superuser.pk).is_active)
