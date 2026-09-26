"""
Tests for the academics app: tenant-scoped CRUD and role-scoped reads.
"""
from django.urls import reverse

from apps.academics.models import (
    AcademicYear, Class, Section, Subject, TimetableEntry,
)
from apps.core.tests import BaseTenantAPITestCase
from apps.students.models import Student
from apps.user_profile.models import UserProfile


class SubjectIsolationTests(BaseTenantAPITestCase):
    def _create_subject(self, name, code):
        return self.client.post(
            reverse("subject-list"),
            {"name": name, "code": code, "credit_hours": 4},
            format="json",
        )

    def test_admin_can_create_and_list_subjects(self):
        self.login(*self.admin_a_creds)
        response = self._create_subject("Mathematics", "MATH-101")
        self.assertEqual(response.status_code, 201, response.content)
        subject = Subject.objects.get(code="MATH-101")
        self.assertEqual(subject.tenant, self.tenant_a)

        listing = self.client.get(reverse("subject-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual([row["code"] for row in listing.data], ["MATH-101"])

    def test_teacher_and_student_can_read_but_not_write(self):
        """Reference data is readable by any tenant member; writes stay admin/HOD."""
        self.login(*self.teacher_a_creds)
        self.assertEqual(self.client.get(reverse("subject-list")).status_code, 200)
        self.assertEqual(self._create_subject("Physics", "PHY-101").status_code, 403)

        self.login(*self.student_a_creds)
        self.assertEqual(self.client.get(reverse("subject-list")).status_code, 200)
        self.assertEqual(self._create_subject("Biology", "BIO-101").status_code, 403)

    def test_teacher_can_populate_dropdowns(self):
        """Teachers need classes/sections/subjects/years to mark attendance and enter results."""
        self.login(*self.teacher_a_creds)
        for url_name in ["class-list", "section-list", "subject-list", "academic-year-list"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, f"{url_name}: {response.content}")

    def test_tenants_cannot_see_each_others_subjects(self):
        self.login(*self.admin_a_creds)
        self.assertEqual(self._create_subject("Alpha Only", "A-ONLY").status_code, 201)
        self.login(*self.admin_b_creds)
        self.assertEqual(self._create_subject("Beta Only", "B-ONLY").status_code, 201)

        self.login(*self.admin_a_creds)
        listing = self.client.get(reverse("subject-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual([row["code"] for row in listing.data], ["A-ONLY"])

        # Object level: Alpha's subject is invisible (404) to Beta's admin.
        alpha_subject = Subject.objects.get(code="A-ONLY")
        self.login(*self.admin_b_creds)
        detail = self.client.get(reverse("subject-detail", args=[alpha_subject.pk]))
        self.assertEqual(detail.status_code, 404)

    def test_admin_cannot_switch_tenant_via_query_param(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("academic-year-list") + f"?tenant_id={self.tenant_b.tenant_id}",
            {"name": "2082-2083", "start_date": "2082-04-01", "end_date": "2083-03-30"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        year = AcademicYear.objects.get(name="2082-2083")
        self.assertEqual(year.tenant, self.tenant_a)


class SubjectClassLinkTests(BaseTenantAPITestCase):
    """Subjects link to the classes that offer them via a many-to-many."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.grade_10 = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 10", numeric_name=10
        )
        cls.grade_8 = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 8", numeric_name=8
        )
        cls.beta_class = Class.objects.create(
            tenant=cls.tenant_b, name="Grade 9", numeric_name=9
        )

    def test_create_subject_with_class_links(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("subject-list"),
            {
                "name": "Mathematics",
                "code": "MATH-101",
                "credit_hours": 4,
                "school_classes": [self.grade_8.pk, self.grade_10.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        subject = Subject.objects.get(code="MATH-101")
        self.assertEqual(
            set(subject.school_classes.values_list("pk", flat=True)),
            {self.grade_8.pk, self.grade_10.pk},
        )
        # class_names are exposed ordered by the class's numeric grade.
        self.assertEqual(
            response.data["class_names"], ["Grade 8", "Grade 10"]
        )

    def test_cross_tenant_class_is_rejected(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("subject-list"),
            {
                "name": "Sneaky",
                "code": "SNK-001",
                "school_classes": [self.beta_class.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("school_classes", response.data)

    def test_update_links_via_patch(self):
        self.login(*self.admin_a_creds)
        subject = Subject.objects.create(
            tenant=self.tenant_a, name="Physics", code="PHY-101"
        )
        subject.school_classes.set([self.grade_8.pk])

        response = self.client.patch(
            reverse("subject-detail", args=[subject.pk]),
            {"school_classes": [self.grade_10.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        subject.refresh_from_db()
        self.assertEqual(
            list(subject.school_classes.values_list("pk", flat=True)),
            [self.grade_10.pk],
        )
        self.assertEqual(response.data["class_names"], ["Grade 10"])


class TimetableRoleScopeTests(BaseTenantAPITestCase):
    """The timetable endpoint is role-scoped, not admin-only.

    Teachers see the periods they teach, students see only their own section,
    and admin/HOD still see every entry (and keep write access).
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import time as dt_time

        super().setUpTestData()
        cls.year = AcademicYear.objects.create(
            tenant=cls.tenant_a, name="2082-2083",
            start_date="2082-04-01", end_date="2083-03-30", is_current=True,
        )
        cls.school_class = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 10", numeric_name=10,
        )
        cls.section_a = Section.objects.create(
            tenant=cls.tenant_a, name="A", school_class=cls.school_class,
        )
        cls.section_b = Section.objects.create(
            tenant=cls.tenant_a, name="B", school_class=cls.school_class,
        )
        cls.maths = Subject.objects.create(tenant=cls.tenant_a, name="Maths", code="M-10")
        cls.english = Subject.objects.create(tenant=cls.tenant_a, name="English", code="E-10")

        # student_a sits in section A. Identity hangs off UserProfile (there is
        # no signal, so the test suite creates the row explicitly) and Student
        # carries the class/section/roll record.
        student_user_profile, _ = UserProfile.objects.get_or_create(
            user_account=cls.student_a,
            defaults={"first_name": "Student", "last_name": "A"},
        )
        cls.student = Student.objects.create(
            tenant=cls.tenant_a, user_profile=student_user_profile,
            school_class=cls.school_class, section=cls.section_a, roll_number=1,
        )

        cls.own_period = TimetableEntry.objects.create(
            tenant=cls.tenant_a, section=cls.section_a, subject=cls.maths,
            teacher=cls.teacher_a, academic_year=cls.year,
            day_of_week="monday", period_number=1,
            start_time=dt_time(9, 0), end_time=dt_time(9, 45),
        )
        cls.other_period = TimetableEntry.objects.create(
            tenant=cls.tenant_a, section=cls.section_b, subject=cls.english,
            teacher=cls.admin_a, academic_year=cls.year,
            day_of_week="monday", period_number=2,
            start_time=dt_time(9, 45), end_time=dt_time(10, 30),
        )

    def test_admin_sees_every_entry(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("timetable-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 2)

    def test_teacher_sees_only_own_periods(self):
        self.login(*self.teacher_a_creds)
        response = self.client.get(reverse("timetable-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row["id"] for row in response.data], [self.own_period.id])

    def test_student_sees_only_own_section(self):
        self.login(*self.student_a_creds)
        response = self.client.get(reverse("timetable-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row["id"] for row in response.data], [self.own_period.id])

    def test_teacher_and_student_cannot_write_timetable(self):
        self.login(*self.teacher_a_creds)
        response = self.client.post(reverse("timetable-list"), {}, format="json")
        self.assertEqual(response.status_code, 403, response.content)

        self.login(*self.student_a_creds)
        response = self.client.post(reverse("timetable-list"), {}, format="json")
        self.assertEqual(response.status_code, 403, response.content)

    def test_other_tenant_cannot_see_this_timetable(self):
        self.login(*self.admin_b_creds)
        response = self.client.get(reverse("timetable-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data, [])
