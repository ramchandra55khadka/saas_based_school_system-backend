"""Create a demo school on the Free plan with one login per role plus sample data.

    python manage.py seed_demo
    python manage.py seed_demo --password 'my-pass' --org-code DEMO

Idempotent: safe to run repeatedly (everything is get_or_create on natural keys).

Operational rules baked into this command:

* It NEVER creates or modifies the platform super admin - that is the job of
  ``bootstrap_superadmin`` / the admin.
* The demo school is subscribed to the **Free** plan, so it only gets the
  Free-plan feature set (students, teachers, academics, reports). Finance and
  communication sample data are therefore NOT seeded, because those features
  are not granted to the Free plan.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.user_profile.models import UserProfile
from apps.parents.models import Parent, StudentGuardian
from apps.academics.models import (
    AcademicYear, Class, Section, Subject, TeacherAssignment, TimetableEntry,
)
from apps.students.models import Exam, ExamResult, Student, StudentAttendance
from apps.subscription.models import Plan, Subscription
from apps.teachers.models import Teacher, TeacherAttendance
from apps.staff.models import Staff
from apps.tenants.models import Tenant

ROLES = {
    "admin": (RoleChoices.ADMIN, "Anita"),
    "hod": (RoleChoices.HOD, "Bikash"),
    "teacher": (RoleChoices.TEACHER, "Chandra"),
    "student": (RoleChoices.STUDENT, "Dipa"),
    "parent": (RoleChoices.PARENT, "Eshan"),
}


class Command(BaseCommand):
    help = "Seed a demo school (Free plan) with one login per core role plus sample data."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-pass-123",
                            help="Password for every demo account.")
        parser.add_argument("--org-code", default="DEMO",
                            help="org_code of the demo school (used as the idempotency key).")
        parser.add_argument("--school-name", default="Demo School")

    def handle(self, *args, **options):
        password = options["password"]
        tenant, _ = Tenant.objects.get_or_create(
            org_code=options["org_code"],
            defaults={"tenant_name": options["school_name"], "address": "Kathmandu"},
        )

        users = self._create_users(tenant, password)
        year, school_class, section, maths, english = self._create_academics(tenant)
        student = self._create_people(tenant, users, school_class, section)
        self._create_timetable(tenant, users, year, section, maths, english)
        self._create_records(tenant, users, student, year, section, maths, english)
        self._create_subscription(tenant)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded '{tenant.tenant_name}' ({tenant.org_code}) on the Free plan — password: {password}"
        ))
        for username, (role, _name) in ROLES.items():
            self.stdout.write(f"  {role:<11} email={username}@demo.test")
        self.stdout.write(
            "  super_admin is NOT created here - run `manage.py bootstrap_superadmin` separately."
        )

    # --------------------------------------------------------------- helpers

    def _create_users(self, tenant, password):
        users = {}
        for username, (role, first_name) in ROLES.items():
            user, _ = UserAccount.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@demo.test"},
            )
            user.email = f"{username}@demo.test"
            user.set_password(password)
            user.save()
            UserProfile.objects.get_or_create(
                user_account=user,
                defaults={"first_name": first_name, "last_name": ""},
            )
            TenantMembership.objects.get_or_create(
                user=user, tenant=tenant, defaults={"role": role, "is_active": True}
            )
            users[username] = user
        return users

    def _create_academics(self, tenant):
        year, _ = AcademicYear.objects.get_or_create(
            tenant=tenant, name="2082-2083",
            defaults={"start_date": date(2025, 4, 1), "end_date": date(2026, 3, 31),
                      "is_current": True},
        )
        school_class, _ = Class.objects.get_or_create(
            tenant=tenant, name="Grade 10", defaults={"numeric_name": 10}
        )
        section, _ = Section.objects.get_or_create(
            tenant=tenant, name="A", school_class=school_class
        )
        maths, _ = Subject.objects.get_or_create(
            tenant=tenant, code="M-10", defaults={"name": "Mathematics", "credit_hours": 4}
        )
        english, _ = Subject.objects.get_or_create(
            tenant=tenant, code="E-10", defaults={"name": "English", "credit_hours": 3}
        )
        return year, school_class, section, maths, english

    def _create_people(self, tenant, users, school_class, section):
        teacher_user_profile = UserProfile.objects.get(user_account=users["teacher"])
        staff_record, _ = Staff.objects.get_or_create(
            tenant=tenant, user_profile=teacher_user_profile,
            defaults={"designation": "teacher", "employee_id": "T-100",
                      "qualification": "master", "specialization": "Mathematics",
                      "date_of_joining": date(2023, 5, 1)},
        )
        Teacher.objects.get_or_create(tenant=tenant, staff=staff_record)

        student_user_profile = UserProfile.objects.get(user_account=users["student"])
        if not student_user_profile.date_of_birth:
            student_user_profile.date_of_birth = date(2009, 8, 20)
            student_user_profile.address = "Kathmandu"
            student_user_profile.save(update_fields=["date_of_birth", "address"])

        student, _ = Student.objects.get_or_create(
            tenant=tenant, user_profile=student_user_profile,
            defaults={"school_class": school_class, "section": section,
                      "roll_number": 7, "admission_date": date(2024, 4, 15),
                      "blood_group": "O+"},
        )

        parent_profile = UserProfile.objects.get(user_account=users["parent"])
        parent, _ = Parent.objects.get_or_create(
            tenant=tenant, user_profile=parent_profile,
            defaults={"occupation": "Engineer", "emergency_contact": "9800000002"},
        )
        StudentGuardian.objects.get_or_create(
            tenant=tenant, student=student, parent=parent,
            defaults={"relation": "father", "is_primary": True},
        )
        return student

    def _create_timetable(self, tenant, users, year, section, maths, english):
        TeacherAssignment.objects.get_or_create(
            tenant=tenant, teacher=users["teacher"], subject=maths,
            section=section, academic_year=year,
        )
        for period, subject in [(1, maths), (2, english)]:
            TimetableEntry.objects.get_or_create(
                tenant=tenant, section=section, day_of_week="monday",
                period_number=period, academic_year=year,
                defaults={"subject": subject, "teacher": users["teacher"],
                          "start_time": time(8 + period, 0),
                          "end_time": time(8 + period, 45)},
            )

    def _create_records(self, tenant, users, student, year, section, maths, english):
        for offset, status in [(0, "present"), (1, "present"), (2, "absent"), (3, "late")]:
            StudentAttendance.objects.get_or_create(
                tenant=tenant, student=student, academic_year=year, section=section,
                date=date.today() - timedelta(days=offset), defaults={"status": status},
            )
        exam, _ = Exam.objects.get_or_create(
            tenant=tenant, name="First Term", academic_year=year,
            defaults={"exam_type": "midterm", "start_date": date(2025, 9, 1),
                      "end_date": date(2025, 9, 10),
                      "description": "First terminal examination"},
        )
        for subject, marks, grade in [(maths, "85.00", "A"), (english, "78.00", "B+")]:
            ExamResult.objects.get_or_create(
                tenant=tenant, exam=exam, student=student, subject=subject,
                defaults={"marks_obtained": Decimal(marks), "max_marks": Decimal("100.00"),
                          "grade": grade, "remarks": "Good work"},
            )
        TeacherAttendance.objects.get_or_create(
            tenant=tenant,
            teacher=Teacher.objects.get(
                staff__user_profile__user_account=users["teacher"]
            ),
            date=date.today(), defaults={"status": "present"},
        )

    def _create_subscription(self, tenant):
        """Put the demo school on the Free plan (the plan is migration-created).

        Plans are otherwise database data owned by super admins - seed never
        creates, prices or caps them. It only (re)points the school's
        subscription at the Free plan.
        """
        plan = Plan.objects.filter(name="Free", is_active=True).first()
        if plan is None:
            self.stdout.write(self.style.WARNING(
                "Free plan not found - run migrations first. Demo school left unsubscribed."
            ))
            return
        subscription, created = Subscription.objects.get_or_create(
            tenant=tenant,
            defaults={"plan": plan, "is_active": True,
                      "end_date": timezone.now() + timedelta(days=plan.duration_days)},
        )
        if not created and (subscription.plan != plan or not subscription.is_active):
            subscription.plan = plan
            subscription.is_active = True
            subscription.end_date = timezone.now() + timedelta(days=plan.duration_days)
            subscription.save()