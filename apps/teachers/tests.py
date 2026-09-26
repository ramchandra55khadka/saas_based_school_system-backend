"""Tests for teacher onboarding.

``POST /api/teachers/profiles/onboard/`` backs the "Add teacher" dialog: the
admin fills the user-profile form, the employment fields and the teaching
extras once, and the endpoint produces the whole chain -- ``UserAccount``,
``UserProfile``, ``TenantMembership``, ``Staff`` and ``Teacher`` -- in one
transaction. The designation is pinned to ``teacher`` (so the membership role
is always a teaching role), subject/section tenancy is enforced and a failure
anywhere leaves nothing behind (see ``TeacherOnboardSerializer``).
"""
from django.urls import reverse

from apps.academics.models import Class, Section, Subject
from apps.core.tests import BaseTenantAPITestCase
from apps.staff.models import Staff
from apps.teachers.constants import TEACHER_ONBOARD_FIELDS
from apps.teachers.models import Teacher
from apps.teachers.serializers import TeacherOnboardSerializer
from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.user_profile.models import UserProfile
from apps.user_profile.serializers import AccountProfileOnboardSerializer


class TeacherOnboardTests(BaseTenantAPITestCase):
    """One request creates the account, profile, staff row and teacher record."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.physics = Subject.objects.create(
            tenant=cls.tenant_a, name="Physics", code="PHY"
        )
        cls.grade_six = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 6", numeric_name=6
        )
        cls.grade_six_a = Section.objects.create(
            tenant=cls.tenant_a, school_class=cls.grade_six, name="A"
        )
        # Another school's reference data: the dialog must not be able to pick it.
        cls.other_school_class = Class.objects.create(
            tenant=cls.tenant_b, name="Grade 6", numeric_name=6
        )
        cls.other_school_subject = Subject.objects.create(
            tenant=cls.tenant_b, name="Chemistry", code="CHM"
        )
        cls.other_school_section = Section.objects.create(
            tenant=cls.tenant_b, school_class=cls.other_school_class, name="A"
        )
        # The base fixture has no HOD; the role tests need one.
        cls.hod_a = UserAccount.objects.create_user(
            username="hod_a", password="hod-a-pass-123", email="hod_a@example.com"
        )
        TenantMembership.objects.create(
            user=cls.hod_a, tenant=cls.tenant_a, role=RoleChoices.HOD
        )

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
            "employee_id": "T-900",
            "qualification": "master",
            "specialization": "Mechanics",
            "date_of_joining": "2026-04-01",
            "teaching_license_number": "LIC-42",
            "primary_subject": self.physics.pk,
            "class_teacher_section": self.grade_six_a.pk,
            "max_weekly_periods": 20,
            "office_hours": "Tue & Thu, 10-12",
            "bio": "Teaches physics and robotics.",
        }
        data.update(overrides)
        # The dialog omits untouched inputs entirely (empty dates, empty files).
        return {key: value for key, value in data.items() if value is not None}

    def onboard(self, **overrides):
        return self.client.post(
            reverse("teacher-profile-onboard"), self.payload(**overrides), format="json"
        )

    def test_admin_onboards_teacher_with_whole_chain(self):
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
        self.assertEqual(profile.address, "Baneshwor, Kathmandu")

        # The membership role is always a teaching role, and the shared staff
        # record carries the employment fields with the teacher designation.
        membership = TenantMembership.objects.get(user=account, tenant=self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.TEACHER)
        self.assertTrue(membership.is_active)

        staff = Staff.objects.get(tenant=self.tenant_a, user_profile=profile)
        self.assertEqual(staff.designation, "teacher")
        self.assertEqual(staff.employee_id, "T-900")
        self.assertEqual(staff.qualification, "master")
        self.assertEqual(staff.specialization, "Mechanics")
        self.assertEqual(str(staff.date_of_joining), "2026-04-01")
        self.assertTrue(staff.is_active)

        teacher = Teacher.objects.get(tenant=self.tenant_a, staff=staff)
        self.assertEqual(teacher.teaching_license_number, "LIC-42")
        self.assertEqual(teacher.primary_subject, self.physics)
        self.assertEqual(teacher.class_teacher_section, self.grade_six_a)
        self.assertEqual(teacher.max_weekly_periods, 20)
        self.assertEqual(teacher.office_hours, "Tue & Thu, 10-12")

        # The response describes the teaching record the dialog just created.
        self.assertEqual(response.data["full_name"], "Ram Bahadur")
        self.assertEqual(response.data["username"], "ram_teacher")
        self.assertEqual(response.data["email"], "ram_teacher@example.com")
        self.assertEqual(response.data["employee_id"], "T-900")
        self.assertEqual(response.data["primary_subject_name"], "Physics")
        self.assertTrue(response.data["is_active"])

    def test_blank_optional_fields_from_the_dialog_are_accepted(self):
        """The dialog sends "" for empty text fields and omits untouched inputs."""
        self.login(*self.admin_a_creds)
        response = self.onboard(
            phone="",
            gender="",
            nationality="",
            address="",
            specialization="",
            qualification="",
            teaching_license_number="",
            office_hours="",
            bio="",
            primary_subject=None,
            class_teacher_section=None,
            max_weekly_periods=None,
            date_of_joining=None,
            date_of_birth=None,
        )
        self.assertEqual(response.status_code, 201, response.content)

        teacher = Teacher.objects.get(staff__user_profile__user_account__username="ram_teacher")
        self.assertEqual(teacher.teaching_license_number, "")
        self.assertIsNone(teacher.primary_subject)
        self.assertIsNone(teacher.class_teacher_section)
        self.assertIsNone(teacher.max_weekly_periods)
        self.assertTrue(teacher.staff.is_active)
        self.assertEqual(teacher.staff.employee_id, "T-900")

    def test_designation_is_pinned_to_teacher(self):
        """Even a hand-crafted payload cannot mint another designation/role."""
        self.login(*self.admin_a_creds)
        response = self.onboard(designation="librarian", role="librarian")
        # The role fails the teacher-designation matrix before anything is
        # written: librarian is not an allowed role for a teaching staff row.
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())

        # Without the bogus role the designation is silently pinned to teacher.
        response = self.onboard(designation="librarian")
        self.assertEqual(response.status_code, 201, response.content)
        teacher = Teacher.objects.get(staff__user_profile__user_account__username="ram_teacher")
        self.assertEqual(teacher.staff.designation, "teacher")

    def test_role_cannot_be_escalated(self):
        """The same escalation matrix as the user-management API applies."""
        self.login(*self.admin_a_creds)
        response = self.onboard(role="admin")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())
        self.assertFalse(Teacher.objects.filter(staff__employee_id="T-900").exists())

        # An admin may, however, grant a teaching-role upgrade (HOD fits the
        # teacher designation and is in the admin's grantable matrix).
        response = self.onboard(role="hod")
        self.assertEqual(response.status_code, 201, response.content)
        account = UserAccount.objects.get(username="ram_teacher")
        membership = TenantMembership.objects.get(user=account, tenant=self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.HOD)

    def test_onboard_covers_every_teacher_field(self):
        """No Teacher column may be unreachable from the add-teacher dialog."""
        model_columns = {field.name for field in Teacher._meta.fields} - {
            "id", "uuid", "tenant", "staff", "created_at", "updated_at",
        }
        self.assertEqual(model_columns, set(TEACHER_ONBOARD_FIELDS))

        # The dialog fields are the teacher columns plus everything the shared
        # staff onboarding already covers ('role' is the membership role, and
        # 'designation' is pinned rather than picked).
        dialog_fields = (
            set(TeacherOnboardSerializer().fields)
            - set(AccountProfileOnboardSerializer().fields)
            - {"role", "designation"}
        )
        self.assertEqual(
            model_columns
            | {"employee_id", "department", "qualification", "specialization",
               "date_of_joining", "is_active"},
            dialog_fields,
        )

    def test_subject_and_section_must_belong_to_the_school(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(primary_subject=self.other_school_subject.pk)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("primary_subject", response.data)

        response = self.onboard(class_teacher_section=self.other_school_section.pk)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("class_teacher_section", response.data)

        # Nothing was written by either attempt.
        self.assertFalse(UserAccount.objects.filter(username="ram_teacher").exists())

    def test_duplicate_username_rejected_cleanly(self):
        """A duplicate username is a clean 400 with no half-committed rows."""
        self.login(*self.admin_a_creds)
        before_accounts = UserAccount.objects.count()
        before_teachers = Teacher.objects.count()
        response = self.onboard(username="admin_a", email="admin_a@example.com")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(UserAccount.objects.count(), before_accounts)
        self.assertEqual(Teacher.objects.count(), before_teachers)

    def test_duplicate_employee_id_rejected_cleanly(self):
        """Staff's unique employee-ID constraint rolls the whole chain back."""
        self.login(*self.admin_a_creds)
        before_accounts = UserAccount.objects.count()
        # ``teacher_a`` in the base fixture already holds T-001 in this school.
        response = self.onboard(employee_id="T-001")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(UserAccount.objects.count(), before_accounts)
        extra = Teacher.objects.filter(staff__employee_id="T-001").exclude(
            staff__user_profile__user_account__username="teacher_a"
        )
        self.assertFalse(extra.exists())

    def test_teacher_role_is_403(self):
        self.login(*self.teacher_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 403, response.content)

    def test_hod_can_onboard_a_teacher(self):
        self.login("hod_a", "hod-a-pass-123")
        response = self.onboard()
        self.assertEqual(response.status_code, 201, response.content)

    def test_super_admin_onboards_into_a_chosen_school(self):
        self.login(*self.super_admin_creds)
        url = reverse("teacher-profile-onboard") + f"?tenant_id={self.tenant_a.tenant_id}"
        response = self.client.post(url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)

        teacher = Teacher.objects.get(staff__user_profile__user_account__username="ram_teacher")
        self.assertEqual(teacher.tenant, self.tenant_a)
        membership = TenantMembership.objects.get(
            user__username="ram_teacher", tenant=self.tenant_a
        )
        self.assertEqual(membership.role, RoleChoices.TEACHER)

    def test_edit_updates_teaching_and_staff_fields(self):
        """The edit dialog PATCHes teaching fields and the shared staff row."""
        self.login(*self.admin_a_creds)
        created = self.onboard()
        self.assertEqual(created.status_code, 201, created.content)

        response = self.client.patch(
            reverse("teacher-profile-detail", kwargs={"pk": created.data["id"]}),
            {
                "bio": "Also coaches the robotics club.",
                "max_weekly_periods": 18,
                "office_hours": "Mon, 2-4",
                "specialization": "Applied physics",
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        teacher = Teacher.objects.get(pk=created.data["id"])
        self.assertEqual(teacher.bio, "Also coaches the robotics club.")
        self.assertEqual(teacher.max_weekly_periods, 18)
        self.assertEqual(teacher.office_hours, "Mon, 2-4")
        self.assertEqual(teacher.staff.specialization, "Applied physics")
        self.assertFalse(teacher.staff.is_active)


class TeacherCreateFromStaffTests(BaseTenantAPITestCase):
    """``POST /api/teachers/profiles/`` with ``staff_id`` adds a teaching record.

    The account and profile already exist on the picked ``staff.Staff`` row, so
    the create reuses them instead of minting a new account/profile.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.physics = Subject.objects.create(
            tenant=cls.tenant_a, name="Physics", code="PHY"
        )
        # A staff member in school A with a teaching membership but no Teacher
        # record yet -- exactly what the picker offers.
        cls.staff_user = UserAccount.objects.create_user(
            username="staff_teacher", password="staff-pass-123",
            email="staff_teacher@example.com",
        )
        TenantMembership.objects.create(
            user=cls.staff_user, tenant=cls.tenant_a, role=RoleChoices.TEACHER
        )
        cls.staff_profile = UserProfile.objects.create(
            user_account=cls.staff_user, first_name="Staff", last_name="Teacher"
        )
        cls.staff = Staff.objects.create(
            tenant=cls.tenant_a, user_profile=cls.staff_profile,
            designation="teacher", employee_id="T-500",
        )

    def test_admin_creates_teacher_from_existing_staff(self):
        self.login(*self.admin_a_creds)
        before_accounts = UserAccount.objects.count()
        response = self.client.post(
            reverse("teacher-profile-list"),
            {
                "staff_id": self.staff.pk,
                "teaching_license_number": "LIC-7",
                "primary_subject": self.physics.pk,
                "max_weekly_periods": 22,
                "office_hours": "Mon, 9-11",
                "bio": "Physics lead.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        # No new account/profile was created: the staff row is reused.
        self.assertEqual(UserAccount.objects.count(), before_accounts)
        teacher = Teacher.objects.get(staff=self.staff)
        self.assertEqual(teacher.primary_subject, self.physics)
        self.assertEqual(teacher.teaching_license_number, "LIC-7")
        self.assertEqual(teacher.max_weekly_periods, 22)
        self.assertEqual(response.data["staff"], self.staff.pk)
        self.assertEqual(response.data["full_name"], "Staff Teacher")

    def test_staff_from_another_school_is_rejected(self):
        other_profile = UserProfile.objects.create(
            user_account=self.admin_b, first_name="Other", last_name="Staff"
        )
        other_staff = Staff.objects.create(
            tenant=self.tenant_b, user_profile=other_profile, designation="teacher"
        )
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("teacher-profile-list"),
            {"staff_id": other_staff.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("staff_id", response.data)

    def test_missing_staff_is_rejected(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("teacher-profile-list"), {"bio": "No staff"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("staff_id", response.data)




