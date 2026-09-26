"""Tests for staff onboarding.

``POST /api/staff/staff/onboard/`` backs the "Add staff member" dialog: the
admin fills the user-profile form and the employment fields once, and the
endpoint has to produce the whole chain -- ``UserAccount``, ``UserProfile``,
``TenantMembership`` and ``Staff`` -- atomically, deriving the membership role
from the designation and enforcing the same escalation matrix as the
user-management API.
"""
import base64

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.tests import BaseTenantAPITestCase
from apps.staff.models import Staff
from apps.staff.serializers import StaffOnboardSerializer
from apps.tenants.models import Department
from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.user_profile.models import UserProfile
from apps.user_profile.serializers import AccountProfileOnboardSerializer

# A real 1x1 PNG: DRF's ImageField validates uploads with Pillow.
ONE_PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA"
    "hKmMIQAAAABJRU5ErkJggg=="
)


class StaffOnboardTests(BaseTenantAPITestCase):
    """One request creates the account, the profile and the staff record."""

    def payload(self, **overrides):
        data = {
            "username": "ram_teacher",
            "email": "ram_teacher@example.com",
            "password": "ram-teacher-pass-123",
            "first_name": "Ram",
            "last_name": "Bahadur",
            "phone": "9800000000",
            "gender": "male",
            "date_of_birth": "1990-05-04",
            "nationality": "Nepali",
            "address": "Baneshwor, Kathmandu",
            "designation": "teacher",
            "employee_id": "T-900",
            "qualification": "master",
            "specialization": "Physics",
            "date_of_joining": "2026-04-01",
        }
        data.update(overrides)
        # The dialog omits a field entirely when its input was left untouched
        # (that is how empty date inputs are sent; DRF rejects "" for dates).
        return {key: value for key, value in data.items() if value is not None}

    def onboard(self, **overrides):
        return self.client.post(
            reverse("staff-onboard"), self.payload(**overrides), format="json"
        )

    def test_admin_onboards_staff_with_account_profile_and_membership(self):
        self.login(*self.admin_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 201, response.content)

        # The form's password works for logging in.
        account = UserAccount.objects.get(username="ram_teacher")
        self.assertTrue(account.check_password("ram-teacher-pass-123"))
        self.assertTrue(account.is_active)

        profile = UserProfile.objects.get(user_account=account)
        self.assertEqual((profile.first_name, profile.last_name), ("Ram", "Bahadur"))
        self.assertEqual(profile.gender, "male")
        self.assertEqual(str(profile.date_of_birth), "1990-05-04")
        self.assertEqual(profile.phone, "9800000000")
        self.assertEqual(profile.nationality, "Nepali")

        membership = TenantMembership.objects.get(user=account, tenant=self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.TEACHER)
        self.assertTrue(membership.is_active)

        staff = Staff.objects.get(tenant=self.tenant_a, user_profile=profile)
        self.assertEqual(staff.designation, "teacher")
        self.assertEqual(staff.employee_id, "T-900")
        self.assertEqual(staff.qualification, "master")
        self.assertEqual(str(staff.date_of_joining), "2026-04-01")
        self.assertTrue(staff.is_active)

        # The response describes the staff record the UI just created.
        self.assertEqual(response.data["user_profile"], profile.pk)
        self.assertEqual(response.data["employee_id"], "T-900")

        listed = self.client.get(reverse("staff-list"))
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertIn(profile.pk, [row["user_profile"] for row in listed.data])

    def test_blank_optional_fields_from_the_dialog_are_accepted(self):
        """The dialog sends "" for empty text fields and omits untouched dates."""
        self.login(*self.admin_a_creds)
        response = self.onboard(
            phone="",
            gender="",
            nationality="",
            address="",
            qualification="",
            specialization="",
            date_of_birth=None,
            date_of_joining=None,
        )
        self.assertEqual(response.status_code, 201, response.content)

        profile = UserProfile.objects.get(user_account__username="ram_teacher")
        self.assertEqual(profile.phone, "")
        self.assertIsNone(profile.date_of_birth)

        staff = Staff.objects.get(tenant=self.tenant_a, user_profile=profile)
        self.assertEqual(staff.qualification, "")
        self.assertIsNone(staff.date_of_joining)
        self.assertTrue(staff.is_active)

    def test_designation_decides_the_membership_role(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(designation="librarian", employee_id="L-1")
        self.assertEqual(response.status_code, 201, response.content)

        account = UserAccount.objects.get(username="ram_teacher")
        self.assertEqual(
            TenantMembership.objects.get(user=account, tenant=self.tenant_a).role,
            RoleChoices.LIBRARIAN,
        )

    def test_explicit_role_must_fit_the_designation(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(role=RoleChoices.ADMIN)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())

    def test_duplicate_username_is_a_clean_400(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(username="admin_a", email="unique@example.com")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(email="unique@example.com").exists())

    def test_duplicate_employee_id_rolls_back_the_new_account(self):
        """Rows written before the staff row must not survive the failure."""
        self.login(*self.admin_a_creds)
        response = self.onboard(employee_id="T-001")  # the baseline teacher's ID
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())
        self.assertFalse(UserProfile.objects.filter(first_name="Ram").exists())
        self.assertFalse(TenantMembership.objects.filter(user__username="ram_teacher").exists())

    def test_department_from_another_school_is_rejected(self):
        other_department = Department.objects.create(tenant=self.tenant_b, name="Science")
        self.login(*self.admin_a_creds)
        response = self.onboard(department=other_department.pk)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())

    def test_teacher_cannot_onboard(self):
        self.login(*self.teacher_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())


    def test_hod_may_only_grant_roles_inside_their_matrix(self):
        hod = UserAccount.objects.create_user(
            username="hod_a", password="hod-a-pass-123", email="hod_a@example.com"
        )
        TenantMembership.objects.create(user=hod, tenant=self.tenant_a, role=RoleChoices.HOD)
        self.login("hod_a", "hod-a-pass-123")

        # A teacher is inside an HOD's matrix ...
        self.assertEqual(self.onboard().status_code, 201)

        # ... support staff (the 'staff' membership role) is not.
        response = self.onboard(
            username="ram_support",
            email="ram_support@example.com",
            designation="support",
            employee_id="S-1",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_support").exists())

    def test_super_admin_onboards_into_a_chosen_school(self):
        self.login(*self.super_admin_creds)
        url = reverse("staff-onboard") + f"?tenant_id={self.tenant_a.tenant_id}"
        response = self.client.post(
            url, self.payload(designation="admin", employee_id="A-1"), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        account = UserAccount.objects.get(username="ram_teacher")
        self.assertEqual(
            TenantMembership.objects.get(user=account, tenant=self.tenant_a).role,
            RoleChoices.ADMIN,
        )
        self.assertTrue(Staff.objects.filter(tenant=self.tenant_a, employee_id="A-1").exists())

    def test_onboard_covers_every_staff_field(self):
        """No Staff column may be unreachable from the add-staff dialog."""
        model_columns = {field.name for field in Staff._meta.fields} - {
            "id", "uuid", "tenant", "user_profile", "created_at", "updated_at",
        }
        # 'role' is the membership role, not a Staff column.
        dialog_fields = (
            set(StaffOnboardSerializer().fields)
            - set(AccountProfileOnboardSerializer().fields)
            - {"role"}
        )
        self.assertEqual(model_columns, dialog_fields)

    def test_profile_image_upload_is_stored_on_the_profile(self):
        """The photo arrives as a file (multipart) and lands on UserProfile."""
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("staff-onboard"),
            {
                **self.payload(designation="teacher"),
                "profile_image": SimpleUploadedFile(
                    "avatar.png", ONE_PX_PNG, content_type="image/png"
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)

        profile = UserProfile.objects.get(user_account__username="ram_teacher")
        self.assertTrue(profile.profile_image.name.startswith("profiles/"))
        # Personal-detail fields ride along on the same multipart request.
        self.assertEqual(profile.nationality, "Nepali")
        self.assertEqual(str(profile.date_of_birth), "1990-05-04")

    def test_department_endpoint_lists_only_the_callers_school(self):
        """The dialog's department select is tenant-scoped like everything else."""
        Department.objects.create(tenant=self.tenant_a, name="Science")
        Department.objects.create(tenant=self.tenant_b, name="Maths")
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("department-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row["name"] for row in response.data], ["Science"])
