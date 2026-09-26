"""
Tests for the user_account app: super-admin tenant onboarding, JWT cookie login
and the platform super-admin access paths.
"""
from django.core.management import call_command
from django.urls import reverse

from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.core.tests import BaseTenantAPITestCase
from apps.tenants.models import Tenant


class TenantOnboardingTests(BaseTenantAPITestCase):
    """POST /api/accounts/superadmin/create-tenant/ (Bug B regression)."""

    def _payload(self, **overrides):
        payload = {
            "tenant_name": "Gamma School",
            "org_code": "GAMMA",
            "address": "Pokhara",
            "admin_username": "gamma_admin",
            "admin_email": "gamma_admin@example.com",
            "admin_password": "gamma-pass-123",
        }
        payload.update(overrides)
        return payload

    def test_super_admin_creates_tenant_and_admin(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("superadmin-create-tenant"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        tenant = Tenant.objects.get(org_code="GAMMA")
        self.assertEqual(tenant.tenant_name, "Gamma School")

        admin = UserAccount.objects.get(username="gamma_admin")
        self.assertTrue(admin.check_password("gamma-pass-123"))
        self.assertTrue(
            TenantMembership.objects.filter(
                user=admin, tenant=tenant, role=RoleChoices.ADMIN, is_active=True
            ).exists()
        )

        # The response must describe what was created (used to 500 here after
        # the rows had already been committed).
        self.assertEqual(response.data["tenant"]["org_code"], "GAMMA")
        self.assertEqual(response.data["admin_user"]["username"], "gamma_admin")

    def test_duplicate_org_code_is_a_clean_400(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("superadmin-create-tenant"), self._payload(org_code="ALPHA"), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Tenant.objects.filter(tenant_name="Gamma School").exists())
        self.assertFalse(UserAccount.objects.filter(username="gamma_admin").exists())

    def test_duplicate_tenant_name_is_a_clean_400(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("superadmin-create-tenant"), self._payload(tenant_name="Alpha School"), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Tenant.objects.filter(org_code="GAMMA").exists())

    def test_duplicate_admin_username_is_a_clean_400(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("superadmin-create-tenant"), self._payload(admin_username="admin_a"), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Tenant.objects.filter(org_code="GAMMA").exists())
        self.assertFalse(UserAccount.objects.filter(email="gamma_admin@example.com").exists())

    def test_tenant_admin_cannot_create_tenants(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("superadmin-create-tenant"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Tenant.objects.filter(org_code="GAMMA").exists())


class LoginTests(BaseTenantAPITestCase):
    """POST /api/accounts/login/ sets the HttpOnly JWT cookie pair."""

    def test_login_sets_jwt_cookies(self):
        response = self.login(*self.admin_a_creds)
        self.assertIn("access", response.cookies)
        self.assertIn("refresh", response.cookies)
        # The view returns the raw tokens in the body only while
        # settings.DEBUG is on — the test runner always forces DEBUG=False,
        # so the HttpOnly cookies are the only credentials handed out here.
        self.assertNotIn("access_token", response.data)
        self.assertNotIn("refresh_token", response.data)

    def test_login_rejects_bad_password(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "admin_a@example.com", "password": "wrong-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 401, response.content)

    def test_login_by_email_and_not_username(self):
        """Login is email-based: a valid email works, a username payload does not."""
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "admin_a@example.com", "password": self.admin_a_creds[1]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("access", response.cookies)

        # The old username-based payload is no longer accepted (missing email).
        username_payload = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "admin_a", "password": self.admin_a_creds[1]},
            format="json",
        )
        self.assertEqual(username_payload.status_code, 400, username_payload.content)

    def test_login_is_case_insensitive_on_email(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "ADMIN_A@EXAMPLE.COM", "password": self.admin_a_creds[1]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_me_endpoint_returns_memberships(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, 200, response.content)
        memberships = response.data["data"]["memberships"]
        self.assertEqual(len(memberships), 1)
        self.assertEqual(memberships[0]["tenant_name"], "Alpha School")
        self.assertEqual(memberships[0]["role"], RoleChoices.ADMIN)


class SecurityHardeningTests(BaseTenantAPITestCase):
    """Production-readiness: token revocation, rotation, cookie flags, bootstrap."""

    def test_refresh_rotates_and_blacklists(self):
        """Each refresh mints a NEW refresh token; the old one becomes unusable."""
        self.login(*self.admin_a_creds)
        old_refresh = self.client.cookies["refresh"].value

        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("refresh", response.cookies)
        self.assertNotEqual(response.cookies["refresh"].value, old_refresh)

        # Replay the now-blacklisted token -> 401.
        self.client.cookies["refresh"] = old_refresh
        replay = self.client.post(reverse("token_refresh"))
        self.assertEqual(replay.status_code, 401, replay.content)

    def test_refresh_works_with_an_expired_access_cookie(self):
        """An expired access cookie must not 401 the refresh endpoint (regression).

        The middleware copies the access cookie into the Authorization header;
        once that access token expires (the exact moment a refresh is needed),
        DRF's JWTAuthentication would raise before the refresh view runs.
        """
        self.login(*self.admin_a_creds)
        self.client.cookies["access"] = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxLCJqdGkiOiJ4In0.x"
        )

        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 200, response.content)

    def test_logout_revokes_the_refresh_token(self):
        """Logout blacklists the refresh token (Bug K regression)."""
        self.login(*self.admin_a_creds)
        stolen_refresh = self.client.cookies["refresh"].value

        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 200, response.content)

        self.client.cookies["refresh"] = stolen_refresh
        replay = self.client.post(reverse("token_refresh"))
        self.assertEqual(replay.status_code, 401, replay.content)

    def test_logout_works_without_authentication(self):
        """Logout must always clear cookies, even with an expired access token."""
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 200, response.content)

    def test_jwt_cookies_secure_outside_debug(self):
        from django.test import override_settings

        with override_settings(DEBUG=False):
            response = self.client.post(
                reverse("token_obtain_pair"),
                {"email": "admin_a@example.com", "password": self.admin_a_creds[1]},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.cookies["access"]["secure"])
        self.assertTrue(response.cookies["refresh"]["secure"])

    def test_jwt_cookies_not_secure_in_dev(self):
        # NOTE: Django's test runner forces DEBUG=False, so opt back in.
        from django.test import override_settings

        with override_settings(DEBUG=True):
            response = self.login(*self.admin_a_creds)
        self.assertFalse(response.cookies["access"]["secure"])

    def test_bootstrap_superadmin_command_is_idempotent(self):
        call_command(
            "bootstrap_superadmin",
            username="cmd_root", email="cmd_root@example.com", password="cmd-pass-123",
        )
        user = UserAccount.objects.get(username="cmd_root")
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertTrue(user.check_password("cmd-pass-123"))

        # Second run: no duplicate, and the password is NOT reset without --force.
        call_command(
            "bootstrap_superadmin",
            username="cmd_root", email="cmd_root@example.com", password="other-pass",
        )
        user.refresh_from_db()
        self.assertEqual(UserAccount.objects.filter(username="cmd_root").count(), 1)
        self.assertTrue(user.check_password("cmd-pass-123"))

        # --force-password does rotate it.
        call_command(
            "bootstrap_superadmin",
            username="cmd_root", email="cmd_root@example.com",
            password="other-pass", force_password=True,
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("other-pass"))
