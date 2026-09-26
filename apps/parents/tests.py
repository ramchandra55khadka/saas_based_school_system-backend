"""Tests for parent onboarding.

``POST /api/parents/parents/onboard/`` backs the "Add parent" dialog: the
admin fills the user-profile form and the guardian-record fields once, and the
endpoint has to produce the whole chain -- ``UserAccount``, ``UserProfile``,
``TenantMembership`` and ``Parent`` -- atomically, granting the ``parent``
membership role and enforcing the same escalation matrix as the
user-management API.
"""
from django.urls import reverse

from apps.core.tests import BaseTenantAPITestCase
from apps.parents.models import Parent
from apps.parents.serializers import ParentOnboardSerializer
from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.user_profile.models import UserProfile
from apps.user_profile.serializers import AccountProfileOnboardSerializer


class ParentOnboardTests(BaseTenantAPITestCase):
    """One request creates the account, the profile and the parent record."""

    def payload(self, **overrides):
        data = {
            "username": "sita_parent",
            "email": "sita_parent@example.com",
            "password": "sita-parent-pass-123",
            "first_name": "Sita",
            "last_name": "Rai",
            "phone": "9800000001",
            "gender": "female",
            "date_of_birth": "1988-01-15",
            "nationality": "Nepali",
            "address": "Patan, Lalitpur",
            "occupation": "Homemaker",
            "emergency_contact": "9900000001",
        }
        data.update(overrides)
        # The dialog omits a field entirely when its input was left untouched
        # (that is how empty date inputs are sent; DRF rejects "" for dates).
        return {key: value for key, value in data.items() if value is not None}

    def onboard(self, **overrides):
        return self.client.post(
            reverse("parent-onboard"), self.payload(**overrides), format="json"
        )

    def test_admin_onboards_parent_with_account_profile_and_membership(self):
        self.login(*self.admin_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 201, response.content)

        # The form's password works for logging in.
        account = UserAccount.objects.get(username="sita_parent")
        self.assertTrue(account.check_password("sita-parent-pass-123"))
        self.assertTrue(account.is_active)

        # Profile holds the personal details flat in the payload.
        profile = UserProfile.objects.get(user_account=account)
        self.assertEqual(profile.first_name, "Sita")
        self.assertEqual(profile.last_name, "Rai")
        self.assertEqual(profile.gender, "female")
        self.assertEqual(profile.address, "Patan, Lalitpur")

        # The membership is active in the tapered tenant with the parent role.
        membership = TenantMembership.objects.get(user=account)
        self.assertEqual(membership.tenant, self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.PARENT)
        self.assertTrue(membership.is_active)

        # The parent record lands on the profile with the guardian fields.
        parent = Parent.objects.get(user_profile=profile)
        self.assertEqual(parent.tenant, self.tenant_a)
        self.assertEqual(parent.occupation, "Homemaker")
        self.assertEqual(parent.emergency_contact, "9900000001")

    def test_duplicate_username_is_rejected(self):
        self.login(*self.admin_a_creds)
        self.assertEqual(self.onboard().status_code, 201)
        response = self.onboard(username="sita_parent", email="sita2@example.com")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("username", response.json())

    def test_creator_cannot_grant_parent_role_when_disallowed(self):
        # A teacher cannot admit a parent; only admin/HOD (or super admin) can.
        # The ``IsAdminOrHOD`` write-permission blocks the action outright (403).
        self.login(*self.teacher_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 403, response.content)

    def test_base_serializer_still_tracks_profile_fields(self):
        # Same guard the staff/student tests rely on: any new UserProfile column
        # must be handled by onboarding payloads, not silently dropped.
        model_fields = {f.name for f in UserProfile._meta.get_fields()}
        onboard_fields = set(AccountProfileOnboardSerializer.PROFILE_FIELDS)
        ignored = model_fields - onboard_fields - {
            "id", "uuid", "user_account", "created_at", "updated_at",
            # Reverse relations hang off the profile but are not payload columns.
            "student", "parent", "staff",
        }
        self.assertEqual(ignored, set())

    def test_serializer_is_account_profile_onboard_class(self):
        self.assertTrue(issubclass(ParentOnboardSerializer, AccountProfileOnboardSerializer))