"""Tests for student onboarding.

``POST /api/students/profiles/onboard/`` backs the "Add student" dialog: the
admin fills the user-profile form and the school-record fields once, and the
endpoint produces the whole chain -- ``UserAccount``, ``UserProfile``,
``TenantMembership`` and ``Student`` -- atomically, always granting the
``student`` membership role, honouring class/section tenancy and stopping at
the plan's ``max_students`` limit (see ``StudentOnboardSerializer``).
"""
from django.urls import reverse

from apps.academics.models import AcademicYear, Class, Section
from apps.core.tests import BaseTenantAPITestCase
from apps.students.models import Student, StudentPromotion
from apps.students.serializers import StudentOnboardSerializer
from apps.subscription.models import Plan
from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.user_profile.models import UserProfile
from apps.user_profile.serializers import AccountProfileOnboardSerializer


class StudentOnboardTests(BaseTenantAPITestCase):
    """One request creates the account, the profile and the student record."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.grade_six = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 6", numeric_name=6
        )
        cls.grade_six_a = Section.objects.create(
            tenant=cls.tenant_a, school_class=cls.grade_six, name="A"
        )
        cls.grade_seven = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 7", numeric_name=7
        )
        cls.grade_seven_b = Section.objects.create(
            tenant=cls.tenant_a, school_class=cls.grade_seven, name="B"
        )
        cls.other_school_class = Class.objects.create(
            tenant=cls.tenant_b, name="Grade 6", numeric_name=6
        )
        # The base fixture has no HOD; the escalation matrix test needs one.
        cls.hod_a = UserAccount.objects.create_user(
            username="hod_a", password="hod-a-pass-123", email="hod_a@example.com"
        )
        TenantMembership.objects.create(
            user=cls.hod_a, tenant=cls.tenant_a, role=RoleChoices.HOD
        )

    def payload(self, **overrides):
        data = {
            "username": "ram_student",
            "email": "ram_student@example.com",
            "password": "ram-student-pass-123",
            "first_name": "Ram",
            "last_name": "Kumari",
            "phone": "9811111111",
            "gender": "female",
            "date_of_birth": "2012-03-15",
            "nationality": "Nepali",
            "address": "Lalitpur, Nepal",
            "school_class": self.grade_six.pk,
            "section": self.grade_six_a.pk,
            "roll_number": 7,
            "admission_date": "2026-04-01",
            "blood_group": "O+",
        }
        data.update(overrides)
        # The dialog omits untouched inputs entirely (empty dates, empty files).
        return {key: value for key, value in data.items() if value is not None}

    def onboard(self, **overrides):
        return self.client.post(
            reverse("student-profile-onboard"), self.payload(**overrides), format="json"
        )

    def test_admin_onboards_student_with_account_profile_and_membership(self):
        self.login(*self.admin_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 201, response.content)

        # The form's password works for logging in.
        account = UserAccount.objects.get(username="ram_student")
        self.assertTrue(account.check_password("ram-student-pass-123"))
        self.assertTrue(account.is_active)

        profile = UserProfile.objects.get(user_account=account)
        self.assertEqual((profile.first_name, profile.last_name), ("Ram", "Kumari"))
        self.assertEqual(profile.phone, "9811111111")
        self.assertEqual(profile.gender, "female")
        self.assertEqual(str(profile.date_of_birth), "2012-03-15")
        self.assertEqual(profile.nationality, "Nepali")
        self.assertEqual(profile.address, "Lalitpur, Nepal")

        membership = TenantMembership.objects.get(user=account, tenant=self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.STUDENT)
        self.assertTrue(membership.is_active)

        student = Student.objects.get(tenant=self.tenant_a, user_profile=profile)
        self.assertEqual(student.school_class, self.grade_six)
        self.assertEqual(student.section, self.grade_six_a)
        self.assertEqual(student.roll_number, 7)
        self.assertEqual(str(student.admission_date), "2026-04-01")
        self.assertEqual(student.blood_group, "O+")

        # The response describes the student record the UI just created.
        self.assertEqual(response.data["user_profile"], profile.pk)
        self.assertEqual(response.data["roll_number"], 7)
        self.assertEqual(response.data["full_name"], "Ram Kumari")
        self.assertEqual(response.data["username"], "ram_student")
        self.assertEqual(response.data["class_name"], "Grade 6")
        self.assertEqual(response.data["section_name"], "A")

    def test_blank_optional_fields_from_the_dialog_are_accepted(self):
        """The dialog sends "" for empty text fields and omits untouched dates."""
        self.login(*self.admin_a_creds)
        response = self.onboard(
            phone="",
            gender="",
            nationality="",
            address="",
            blood_group="",
            school_class=None,
            section=None,
            roll_number=None,
            admission_date=None,
            date_of_birth=None,
        )
        self.assertEqual(response.status_code, 201, response.content)

        profile = UserProfile.objects.get(user_account__username="ram_student")
        self.assertEqual(profile.phone, "")
        self.assertIsNone(profile.date_of_birth)

        student = Student.objects.get(tenant=self.tenant_a, user_profile=profile)
        self.assertIsNone(student.school_class)
        self.assertIsNone(student.section)
        self.assertIsNone(student.roll_number)
        self.assertIsNone(student.admission_date)
        self.assertEqual(student.blood_group, "")

    def test_role_field_cannot_escalate_the_new_student(self):
        """There is no role input: onboarding always grants 'student'."""
        self.login(*self.admin_a_creds)
        response = self.onboard(role=RoleChoices.ADMIN)
        self.assertEqual(response.status_code, 201, response.content)

        account = UserAccount.objects.get(username="ram_student")
        membership = TenantMembership.objects.get(user=account, tenant=self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.STUDENT)

    def test_onboard_covers_every_student_field(self):
        """No Student column may be unreachable from the add-student dialog."""
        model_columns = {field.name for field in Student._meta.fields} - {
            "id", "uuid", "tenant", "user_profile", "created_at", "updated_at",
        }
        dialog_fields = set(StudentOnboardSerializer().fields) - set(
            AccountProfileOnboardSerializer().fields
        )
        self.assertEqual(model_columns, dialog_fields)

    def test_section_must_belong_to_the_selected_class(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(section=self.grade_seven_b.pk)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_student").exists())

    def test_class_from_another_school_is_rejected(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(school_class=self.other_school_class.pk, section=None)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_student").exists())

    def test_duplicate_username_is_a_clean_400(self):
        self.login(*self.admin_a_creds)
        response = self.onboard(username="admin_a", email="unique@example.com")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(email="unique@example.com").exists())

    def test_duplicate_roll_number_rolls_back_the_new_account(self):
        """Rows written before the student row must not survive the failure."""
        self.login(*self.admin_a_creds)
        self.assertEqual(self.onboard().status_code, 201)

        response = self.onboard(
            username="ram_student_2", email="ram_student_2@example.com"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_student_2").exists())
        self.assertEqual(Student.objects.filter(tenant=self.tenant_a).count(), 1)

    def test_teacher_cannot_onboard(self):
        self.login(*self.teacher_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(UserAccount.objects.filter(username="ram_student").exists())

    def test_hod_may_onboard_a_student(self):
        """An HOD's matrix covers teacher and student -- admissions included."""
        self.login("hod_a", "hod-a-pass-123")
        response = self.onboard()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(
            Student.objects.filter(tenant=self.tenant_a, roll_number=7).exists()
        )

    def test_super_admin_onboards_into_a_chosen_school(self):
        self.login(*self.super_admin_creds)
        url = reverse("student-profile-onboard") + f"?tenant_id={self.tenant_a.tenant_id}"
        response = self.client.post(url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)

        account = UserAccount.objects.get(username="ram_student")
        membership = TenantMembership.objects.get(user=account, tenant=self.tenant_a)
        self.assertEqual(membership.role, RoleChoices.STUDENT)

    def test_plan_student_limit_stops_onboarding_before_any_write(self):
        plan = Plan.objects.create(
            name="Tiny", price=0, duration_days=30, max_students=1, is_active=True
        )
        plan.features.set(self.default_features.values())
        self._subscribe(self.tenant_a, plan)

        # The school is already at its cap.
        existing_profile, _ = UserProfile.objects.get_or_create(
            user_account=self.student_a, defaults={"first_name": "Existing"}
        )
        Student.objects.create(tenant=self.tenant_a, user_profile=existing_profile)

        self.login(*self.admin_a_creds)
        response = self.onboard()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("maximum of 1 students", str(response.data))
        # Nothing was written: the account does not exist either.
        self.assertFalse(UserAccount.objects.filter(username="ram_student").exists())
        self.assertFalse(
            TenantMembership.objects.filter(user__username="ram_student").exists()
        )


class StudentPromotionTests(BaseTenantAPITestCase):
    """``StudentPromotionViewSet.perform_create`` must stamp the tenant."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.grade_9 = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 9", numeric_name=9
        )
        cls.grade_10 = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 10", numeric_name=10
        )
        cls.year_from = AcademicYear.objects.create(
            tenant=cls.tenant_a, name="2082-2083",
            start_date="2025-04-13", end_date="2026-04-12",
        )
        cls.year_to = AcademicYear.objects.create(
            tenant=cls.tenant_a, name="2083-2084",
            start_date="2026-04-13", end_date="2027-04-12", is_current=True,
        )
        profile, _ = UserProfile.objects.get_or_create(
            user_account=cls.student_a, defaults={"first_name": "Promotable"}
        )
        cls.student = Student.objects.create(
            tenant=cls.tenant_a, user_profile=profile
        )

    def promote(self):
        return self.client.post(
            reverse("student-promotion-list"),
            {
                "student": self.student.pk,
                "from_class": self.grade_9.pk,
                "to_class": self.grade_10.pk,
                "from_academic_year": self.year_from.pk,
                "to_academic_year": self.year_to.pk,
                "remarks": "Promoted on final results.",
            },
            format="json",
        )

    def test_admin_promotion_stamps_the_tenant(self):
        self.login(*self.admin_a_creds)
        response = self.promote()
        self.assertEqual(response.status_code, 201, response.content)
        promo = StudentPromotion.objects.get(student=self.student)
        self.assertEqual(promo.tenant_id, self.tenant_a.tenant_id)
        self.assertEqual(promo.promoted_by_id, self.admin_a.id)
        self.assertEqual(promo.to_class, self.grade_10)

    def test_student_cannot_promote(self):
        self.login("student_a", "student-a-pass-123")
        response = self.promote()
        self.assertEqual(response.status_code, 403, response.content)
