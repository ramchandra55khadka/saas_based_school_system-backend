"""School profile read/edit tests for the super-admin dashboard."""
import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.core.tests import BaseTenantAPITestCase
from apps.subscription.models import Subscription
from apps.tenants.models import Department, Tenant
from apps.user_account.models import RoleChoices, TenantMembership, UserAccount

MEDIA_ROOT = tempfile.mkdtemp(prefix="test-media-")


def tiny_png():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SchoolProfileUpdateTests(BaseTenantAPITestCase):
    """PATCH /api/tenants/profile/{tenant_id}/ — the dashboard edit path."""

    def _url(self, tenant):
        return reverse("school-profile-detail", args=[tenant.tenant_id])

    def test_super_admin_can_patch_profile_fields(self):
        self.login(*self.super_admin_creds)
        response = self.client.patch(
            self._url(self.tenant_a),
            {
                "tenant_name": "Alpha School Renamed",
                "phone": "+977-1-4000000",
                "email": "info@alpha.example",
                "website": "https://alpha.example",
                "address": "Pokhara, Nepal",
                "established_year": 1985,
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.tenant_a.refresh_from_db()
        self.assertEqual(self.tenant_a.tenant_name, "Alpha School Renamed")
        self.assertEqual(self.tenant_a.phone, "+977-1-4000000")
        self.assertEqual(self.tenant_a.email, "info@alpha.example")
        self.assertEqual(self.tenant_a.website, "https://alpha.example")
        self.assertEqual(self.tenant_a.established_year, 1985)
        self.assertFalse(self.tenant_a.is_active)

    def test_super_admin_can_clear_established_year(self):
        self.tenant_a.established_year = 1985
        self.tenant_a.save(update_fields=["established_year"])

        self.login(*self.super_admin_creds)
        response = self.client.patch(
            self._url(self.tenant_a), {"established_year": None}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.tenant_a.refresh_from_db()
        self.assertIsNone(self.tenant_a.established_year)

    def test_invalid_website_is_a_clean_400(self):
        self.login(*self.super_admin_creds)
        response = self.client.patch(
            self._url(self.tenant_a), {"website": "not-a-url"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("website", response.data)

    def test_logo_can_be_uploaded_via_multipart_patch(self):
        self.login(*self.super_admin_creds)
        response = self.client.patch(
            self._url(self.tenant_a),
            {"logo": SimpleUploadedFile("logo.png", tiny_png(), content_type="image/png")},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.tenant_a.refresh_from_db()
        self.assertTrue(self.tenant_a.logo)
        self.assertIn("logo", response.data)

    def test_tenant_admin_can_edit_own_school(self):
        self.login(*self.admin_a_creds)
        response = self.client.patch(
            self._url(self.tenant_a),
            {"phone": "+977-9800000001"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.tenant_a.refresh_from_db()
        self.assertEqual(self.tenant_a.phone, "+977-9800000001")

    def test_tenant_admin_cannot_edit_another_school(self):
        self.login(*self.admin_a_creds)
        response = self.client.patch(
            self._url(self.tenant_b), {"phone": "+977-hacked"}, format="json"
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_tenant_admin_cannot_see_other_schools_in_list(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("school-profile-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row["tenant_name"] for row in response.data], ["Alpha School"])

    def test_anonymous_patch_is_401(self):
        response = self.client.patch(
            self._url(self.tenant_a), {"phone": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 401, response.content)

    def test_list_returns_profile_fields(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(reverse("school-profile-list"))
        self.assertEqual(response.status_code, 200, response.content)
        row = next(r for r in response.data if r["tenant_id"] == str(self.tenant_a.tenant_id))
        for field in (
            "tenant_name", "org_code", "address", "phone", "email",
            "website", "logo", "established_year", "is_active", "created_at",
        ):
            self.assertIn(field, row)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TenantOnboardingProfileFieldsTests(BaseTenantAPITestCase):
    """create-tenant accepts every Tenant profile field (multipart or JSON)."""

    def _payload(self):
        return {
            "tenant_name": "Delta School",
            "org_code": "DELTA",
            "address": "Lakeside, Pokhara",
            "phone": "+977-61-400000",
            "email": "info@delta.example",
            "website": "https://delta.example",
            "established_year": "1992",
            "admin_username": "delta_admin",
            "admin_email": "delta_admin@example.com",
            "admin_password": "delta-pass-123",
        }

    def test_create_tenant_with_all_profile_fields(self):
        self.login(*self.super_admin_creds)
        payload = self._payload()
        payload["logo"] = SimpleUploadedFile(
            "delta.png", tiny_png(), content_type="image/png"
        )
        response = self.client.post(reverse("superadmin-create-tenant"), payload)
        self.assertEqual(response.status_code, 201, response.content)

        tenant = Tenant.objects.get(org_code="DELTA")
        self.assertEqual(tenant.phone, "+977-61-400000")
        self.assertEqual(tenant.email, "info@delta.example")
        self.assertEqual(tenant.website, "https://delta.example")
        self.assertEqual(tenant.established_year, 1992)
        self.assertTrue(tenant.logo)
        self.assertEqual(response.data["tenant"]["phone"], "+977-61-400000")
        self.assertEqual(response.data["tenant"]["established_year"], 1992)

    def test_create_tenant_still_works_without_new_fields(self):
        """Back-compat: the old minimal JSON payload remains valid."""
        self.login(*self.super_admin_creds)
        payload = self._payload()
        for key in ("phone", "email", "website", "established_year"):
            payload.pop(key)
        response = self.client.post(
            reverse("superadmin-create-tenant"), payload, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        tenant = Tenant.objects.get(org_code="DELTA")
        self.assertEqual(tenant.phone, "")
        self.assertEqual(tenant.email, "")
        self.assertEqual(tenant.website, "")
        self.assertIsNone(tenant.established_year)
        self.assertFalse(tenant.logo)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SchoolDeleteTests(BaseTenantAPITestCase):
    """DELETE /api/tenants/profile/{tenant_id}/ — super-admin only, destructive.

    Deletion cascades (tenant-scoped records are wiped via CASCADE), so it is
    gated on the IsSuperAdmin permission while tenant admins keep view/update.
    """

    def _url(self, tenant):
        return reverse("school-profile-detail", args=[tenant.tenant_id])

    def test_super_admin_can_delete_school(self):
        # A subscribed school is the interesting case: deleting the tenant must
        # cascade-delete its Subscription so the platform list stops showing it.
        subscription = self._subscribe(self.tenant_a)

        self.login(*self.super_admin_creds)
        before = self.client.get(reverse("subscription-list"))
        self.assertIn(subscription.id, [row["id"] for row in before.data])

        response = self.client.delete(self._url(self.tenant_a))
        self.assertEqual(response.status_code, 204, response.content)

        # Super-admin school list must no longer include the deleted school.
        listing = self.client.get(reverse("school-profile-list"))
        ids = [row["tenant_id"] for row in listing.data]
        self.assertNotIn(str(self.tenant_a.tenant_id), ids)

        # ...and neither must the platform subscription list (cascade delete).
        after = self.client.get(reverse("subscription-list"))
        self.assertNotIn(subscription.id, [row["id"] for row in after.data])
        self.assertFalse(
            Subscription.objects.filter(tenant=self.tenant_a).exists()
        )

    def test_tenant_admin_cannot_delete(self):
        self.login(*self.admin_a_creds)
        response = self.client.delete(self._url(self.tenant_a))
        self.assertEqual(response.status_code, 403, response.content)
        self.assertTrue(Tenant.objects.filter(tenant_id=self.tenant_a.tenant_id).exists())

    def test_tenant_admin_cannot_delete_another_school(self):
        self.login(*self.admin_a_creds)
        response = self.client.delete(self._url(self.tenant_b))
        # deletion is super-admin-only across the whole endpoint, so any
        # non-super-admin request is rejected with 403 before the object is
        # loaded — no existence leak, just a clear "no permission".
        self.assertEqual(response.status_code, 403, response.content)
        self.assertTrue(Tenant.objects.filter(tenant_id=self.tenant_b.tenant_id).exists())

    def test_anonymous_delete_is_401(self):
        response = self.client.delete(self._url(self.tenant_a))
        self.assertEqual(response.status_code, 401, response.content)


class DepartmentManagementTests(BaseTenantAPITestCase):
    """``/api/tenants/departments/`` — the Academics → Departments tab.

    Reads are open to every member of the school (the staff form and the teacher
    onboarding dialog both use the list as a pick-list), while create/update/
    delete follow the same matrix as the rest of the admin API: admin, principal
    and HOD — plus the platform super admin. A department always belongs to the
    caller's active school: the API fills ``tenant`` in from the JWT claim, so
    the payload never carries one.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hod_a = UserAccount.objects.create_user(
            username="hod_a",
            password="hod-a-pass-123",
            email="hod_a@example.com",
        )
        TenantMembership.objects.create(
            user=cls.hod_a, tenant=cls.tenant_a, role=RoleChoices.HOD
        )

    @staticmethod
    def _payload(**overrides):
        payload = {"name": "Science", "level": "secondary"}
        payload.update(overrides)
        return payload

    def test_admin_creates_a_department_in_their_own_school(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("department-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        department = Department.objects.get(name="Science")
        self.assertEqual(department.tenant, self.tenant_a)
        self.assertEqual(department.level, "secondary")
        self.assertTrue(department.is_active)
        self.assertEqual(response.data["level"], "secondary")
        # The tenant is implied by the active school, not sent by the client.
        self.assertNotIn("tenant", response.data)

    def test_level_defaults_to_other(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("department-list"), {"name": "General"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        department = Department.objects.get(name="General")
        self.assertEqual(department.level, "other")
        self.assertEqual(department.description, "")

    def test_duplicate_name_in_the_same_school_is_a_clean_400(self):
        Department.objects.create(tenant=self.tenant_a, name="Science")
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("department-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("name", response.data)
        self.assertEqual(Department.objects.filter(tenant=self.tenant_a).count(), 1)

    def test_duplicate_name_is_rejected_case_insensitively(self):
        Department.objects.create(tenant=self.tenant_a, name="Science")
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("department-list"), self._payload(name="science"), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Department.objects.filter(tenant=self.tenant_a).count(), 1)

    def test_super_admin_must_pass_tenant_id_to_create(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("department-list"), self._payload(), format="json"
        )
        # No active school -> a clear 400 instead of a 500 from the FK.
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Department.objects.exists())

        scoped = self.client.post(
            reverse("department-list") + f"?tenant_id={self.tenant_a.tenant_id}",
            self._payload(),
            format="json",
        )
        self.assertEqual(scoped.status_code, 201, scoped.content)
        self.assertEqual(Department.objects.get(name="Science").tenant, self.tenant_a)

    def test_the_same_name_is_allowed_in_another_school(self):
        Department.objects.create(tenant=self.tenant_a, name="Science")
        self.login(*self.admin_b_creds)
        response = self.client.post(
            reverse("department-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(
            Department.objects.filter(tenant=self.tenant_b, name="Science").exists()
        )

    def test_invalid_level_is_a_clean_400(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("department-list"),
            self._payload(level="not-a-level"),
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("level", response.data)

    def test_hod_can_create_departments(self):
        self.login("hod_a", "hod-a-pass-123")
        response = self.client.post(
            reverse("department-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Department.objects.get(name="Science").tenant, self.tenant_a)

    def test_teacher_cannot_create_a_department(self):
        self.login(*self.teacher_a_creds)
        response = self.client.post(
            reverse("department-list"), self._payload(name="Arts"), format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Department.objects.filter(name="Arts").exists())

    def test_teacher_can_read_the_pick_list(self):
        Department.objects.create(tenant=self.tenant_a, name="Science")
        self.login(*self.teacher_a_creds)
        response = self.client.get(reverse("department-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row["name"] for row in response.data], ["Science"])

    def test_departments_are_tenant_scoped(self):
        own = Department.objects.create(tenant=self.tenant_a, name="Science")
        other = Department.objects.create(tenant=self.tenant_b, name="Beta Only")

        self.login(*self.admin_a_creds)
        listing = self.client.get(reverse("department-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual([row["name"] for row in listing.data], ["Science"])

        # Another school's row is unreachable by id...
        hijack = self.client.patch(
            reverse("department-detail", args=[other.pk]),
            {"name": "Hijacked"},
            format="json",
        )
        self.assertEqual(hijack.status_code, 404, hijack.content)
        other.refresh_from_db()
        self.assertEqual(other.name, "Beta Only")

        # ...while the school's own row stays editable.
        edit = self.client.patch(
            reverse("department-detail", args=[own.pk]),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(edit.status_code, 200, edit.content)

    def test_admin_can_update_and_delete_a_department(self):
        department = Department.objects.create(tenant=self.tenant_a, name="Science")
        self.login(*self.admin_a_creds)

        update = self.client.patch(
            reverse("department-detail", args=[department.pk]),
            {
                "name": "Science & Technology",
                "description": "Physics, chemistry and biology labs.",
            },
            format="json",
        )
        self.assertEqual(update.status_code, 200, update.content)
        department.refresh_from_db()
        self.assertEqual(department.name, "Science & Technology")
        self.assertEqual(department.description, "Physics, chemistry and biology labs.")

        delete = self.client.delete(reverse("department-detail", args=[department.pk]))
        self.assertEqual(delete.status_code, 204, delete.content)
        self.assertFalse(Department.objects.filter(pk=department.pk).exists())

    def test_anonymous_requests_are_401(self):
        self.assertEqual(
            self.client.post(
                reverse("department-list"), self._payload(), format="json"
            ).status_code,
            401,
        )
        self.assertEqual(self.client.get(reverse("department-list")).status_code, 401)
