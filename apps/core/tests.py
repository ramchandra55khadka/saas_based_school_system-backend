"""
Regression suite for the tenant-scoped API.

These tests pin the behaviour that historical bugs broke:

* **Bug A** - ``TenantRequiredMixin`` used to read ``request.user`` inside
  ``dispatch()``, i.e. on the *raw* Django request before DRF had run JWT
  authentication, so every tenant-scoped endpoint answered
  ``401 {"detail": "Authentication required"}`` even with a valid token.
* **Tenant isolation** - every queryset must be scoped to the JWT's
  ``active_tenant_id`` claim; a tenant admin must never see another school's
  rows, and ``?tenant_id=`` must be honoured for super admins only.

The tests drive the real stack end to end: cookie login ->
``user_account.middleware.CustomJWTMiddleware`` copies the cookie to an
``Authorization`` header -> SimpleJWT authenticates -> the mixin resolves
``request.tenant`` from the token claim.
"""
from datetime import timedelta
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.user_account.models import RoleChoices, TenantMembership, UserAccount
from apps.user_profile.models import UserProfile
from apps.staff.models import Staff
from apps.academics.models import AcademicYear
from apps.students.models import Student
from apps.subscription.constants import FeatureKey
from apps.subscription.models import Feature, Plan, Subscription
from apps.teachers.models import LeaveRequest, Teacher
from apps.tenants.models import Tenant


class CsrfAwareAPIClient(APIClient):
    """Test client that mirrors the browser's double-submit CSRF header.

    ``CookieJWTCSRFMiddleware`` requires an unsafe request that carries an auth
    cookie to also echo the ``csrf_token`` cookie back in ``X-CSRFToken`` — which
    ``src/lib/api.ts`` does for real callers. The token is re-minted on every
    refresh, so it is read from the cookie jar per request instead of being
    captured once at login.
    """

    UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def request(self, **kwargs):
        # Mirrors ``rest_framework.test.APIClient.request``, which is
        # keyword-only and receives Django-style request kwargs.
        method = str(kwargs.get("REQUEST_METHOD", "")).upper()
        if method in self.UNSAFE_METHODS and "HTTP_X_CSRFTOKEN" not in kwargs:
            cookie_name = getattr(settings, "JWT_CSRF_COOKIE", "csrf_token")
            token = self.cookies.get(cookie_name)
            if token is not None:
                kwargs["HTTP_X_CSRFTOKEN"] = token.value
        return super().request(**kwargs)


class BaseTenantAPITestCase(TestCase):
    """Two schools, one super admin, and a full set of roles per school."""

    super_admin_creds = ("root", "root-pass-123")
    admin_a_creds = ("admin_a", "admin-a-pass-123")
    admin_b_creds = ("admin_b", "admin-b-pass-123")
    teacher_a_creds = ("teacher_a", "teacher-a-pass-123")
    student_a_creds = ("student_a", "student-a-pass-123")
    parent_a_creds = ("parent_a", "parent-a-pass-123")
    nomad_creds = ("nomad", "nomad-pass-123")

    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(tenant_name="Alpha School", org_code="ALPHA")
        cls.tenant_b = Tenant.objects.create(tenant_name="Beta School", org_code="BETA")

        cls.super_admin = cls._user(*cls.super_admin_creds, None, "root@example.com", is_superuser=True)
        cls.admin_a = cls._user(*cls.admin_a_creds, RoleChoices.ADMIN, "admin_a@example.com")
        cls.admin_b = cls._user(*cls.admin_b_creds, RoleChoices.ADMIN, "admin_b@example.com")
        cls.teacher_a = cls._user(*cls.teacher_a_creds, RoleChoices.TEACHER, "teacher_a@example.com")
        cls.student_a = cls._user(*cls.student_a_creds, RoleChoices.STUDENT, "student_a@example.com")
        cls.parent_a = cls._user(*cls.parent_a_creds, RoleChoices.PARENT, "parent_a@example.com")
        # A teacher account with no TenantMembership: login succeeds but the
        # token carries no active_tenant_id claim.
        cls.nomad = cls._user(*cls.nomad_creds, RoleChoices.TEACHER, "nomad@example.com")

        TenantMembership.objects.create(user=cls.admin_a, tenant=cls.tenant_a, role=RoleChoices.ADMIN)
        TenantMembership.objects.create(user=cls.admin_b, tenant=cls.tenant_b, role=RoleChoices.ADMIN)
        TenantMembership.objects.create(user=cls.teacher_a, tenant=cls.tenant_a, role=RoleChoices.TEACHER)
        TenantMembership.objects.create(user=cls.student_a, tenant=cls.tenant_a, role=RoleChoices.STUDENT)
        TenantMembership.objects.create(user=cls.parent_a, tenant=cls.tenant_a, role=RoleChoices.PARENT)

        teacher_user_profile, _ = UserProfile.objects.get_or_create(
            user_account=cls.teacher_a,
            defaults={"first_name": "Teacher", "last_name": "A"},
        )
        teacher_staff, _ = Staff.objects.get_or_create(
            tenant=cls.tenant_a, user_profile=teacher_user_profile,
            defaults={"designation": "teacher", "employee_id": "T-001"},
        )
        cls.teacher_a_profile = Teacher.objects.create(
            tenant=cls.tenant_a, staff=teacher_staff,
        )
        cls.plan = Plan.objects.create(name="Basic", price=100, duration_days=365, max_students=500)
        # Grant the shared test plan every feature so role/tenant tests (which
        # are not about entitlements) keep exercising the whole UI surface.
        cls.default_features = {
            fk: Feature.objects.get_or_create(key=fk, defaults={"name": fk.label})[0]
            for fk in (
                FeatureKey.STUDENTS,
                FeatureKey.TEACHERS,
                FeatureKey.STAFF,
                FeatureKey.PARENTS,
                FeatureKey.ACADEMICS,
                FeatureKey.COMMUNICATION,
                FeatureKey.FINANCE,
                FeatureKey.LIBRARY,
                FeatureKey.REPORTS,
            )
        }
        cls.plan.features.set(cls.default_features.values())

    @staticmethod
    def _user(username, password, role, email, is_superuser=False):
        return UserAccount.objects.create_user(
            username=username, password=password, email=email,
            is_staff=is_superuser,
            is_superuser=is_superuser,
        )

    @classmethod
    def _subscribe(cls, tenant, plan=None):
        """Give ``tenant`` an active subscription, granting its plan's features."""
        return Subscription.objects.create(
            tenant=tenant,
            plan=plan or cls.plan,
            end_date=timezone.now() + timedelta(days=365),
            is_active=True,
        )

    def setUp(self):
        self.client = CsrfAwareAPIClient()

    def login(self, username, password, tenant=None):
        """Log in through the real endpoints, in the correct login context.

        Mirrors the browser: a school user signs in **on their school's
        subdomain** via ``/api/auth/login/``, a platform super admin on the
        platform host via ``/api/auth/super-user/login/``. The two endpoints
        are deliberately not interchangeable, so the context is derived here
        rather than left to the call site.

        The school is conveyed with ``HTTP_X_TENANT_HOST`` — the same header the
        Next.js proxy sets in production — so the test exercises the real
        ``TenantMiddleware`` path instead of a test-only shortcut.

        Login is email-based; every user created in this suite follows the
        ``{username}@example.com`` convention. The HttpOnly ``access`` cookie
        stays in the test client and is promoted to an ``Authorization`` header
        by the custom middleware - exactly what happens in the browser.
        """
        email = f"{username}@example.com"
        user = UserAccount.objects.get(email__iexact=email)

        if user.is_superuser:
            url, extra = reverse("super_user_login"), {}
        else:
            if tenant is None:
                membership = (
                    user.memberships.filter(is_active=True)
                    .select_related("tenant")
                    .first()
                )
                self.assertIsNotNone(
                    membership,
                    f"{username} has no active membership; pass tenant= explicitly "
                    f"to exercise a rejected tenant login.",
                )
                tenant = membership.tenant
            url = reverse("auth_login")
            extra = {
                "HTTP_X_TENANT_HOST": (
                    f"{tenant.slug}.{settings.TENANT_ROOT_DOMAIN}"
                )
            }

        response = self.client.post(
            url,
            {"email": email, "password": password},
            format="json",
            **extra,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def tenant_host(self, tenant):
        """The ``HTTP_X_TENANT_HOST`` value that resolves to ``tenant``."""
        return f"{tenant.slug}.{settings.TENANT_ROOT_DOMAIN}"

class TenantAuthenticationTests(BaseTenantAPITestCase):
    """Bug A regression: the tenant API must work with a valid JWT cookie."""

    def test_anonymous_request_is_401(self):
        response = self.client.get(reverse("academic-year-list"))
        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(response.data["detail"], "Authentication required")

    def test_valid_cookie_reaches_tenant_api(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("academic-year-list"))
        self.assertEqual(response.status_code, 200, response.content)

    def test_user_without_membership_cannot_get_a_tenant_token(self):
        """An account with no membership is refused at login, not after it.

        The old single ``/api/accounts/login/`` endpoint let such an account log
        in and mint a claim-less token, which only surfaced later as a 400 from
        the first tenant-scoped endpoint. Tenant login now rejects it up front.
        """
        response = self.client.post(
            reverse("auth_login"),
            {"email": "nomad@example.com", "password": self.nomad_creds[1]},
            format="json",
            HTTP_X_TENANT_HOST=self.tenant_host(self.tenant_a),
        )
        # A generic 401, not a 400: the response must not reveal that the
        # account exists but merely lacks a membership in this school.
        self.assertEqual(response.status_code, 401, response.content)
        self.assertNotIn("access", response.cookies)


class TenantIsolationTests(BaseTenantAPITestCase):
    """Data created in one school must be invisible to the other school."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.year_a = AcademicYear.objects.create(
            tenant=cls.tenant_a, name="2082-2083",
            start_date="2082-04-01", end_date="2083-03-30",
        )
        cls.year_b = AcademicYear.objects.create(
            tenant=cls.tenant_b, name="2082-2083",
            start_date="2082-04-01", end_date="2083-03-30",
        )

    def test_list_is_scoped_to_the_callers_tenant(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("academic-year-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "2082-2083")

    def test_detail_of_another_tenants_row_is_404(self):
        self.login(*self.admin_b_creds)
        response = self.client.get(reverse("academic-year-detail", args=[self.year_a.pk]))
        self.assertEqual(response.status_code, 404, response.content)

    def test_created_row_is_stamped_with_the_callers_tenant(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("academic-year-list"),
            {"name": "2083-2084", "start_date": "2083-04-01", "end_date": "2084-03-30"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        year = AcademicYear.objects.get(name="2083-2084")
        self.assertEqual(year.tenant, self.tenant_a)

    def test_query_param_tenant_id_is_super_admin_only(self):
        """A tenant admin passing ?tenant_id=<other school> must NOT switch."""
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("academic-year-list") + f"?tenant_id={self.tenant_b.tenant_id}",
            {"name": "2084-2085", "start_date": "2084-04-01", "end_date": "2085-03-30"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        year = AcademicYear.objects.get(name="2084-2085")
        self.assertEqual(year.tenant, self.tenant_a)


class SuperAdminAccessTests(BaseTenantAPITestCase):
    """The super admin is platform-level and acts on schools via ?tenant_id=."""

    def test_super_admin_sees_all_schools_in_profile_list(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(reverse("school-profile-list"))
        self.assertEqual(response.status_code, 200, response.content)
        names = {row["tenant_name"] for row in response.data}
        self.assertEqual(names, {"Alpha School", "Beta School"})

    def test_super_admin_acts_on_a_school_via_tenant_id_query(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("academic-year-list") + f"?tenant_id={self.tenant_a.tenant_id}",
            {"name": "2082-2083", "start_date": "2082-04-01", "end_date": "2083-03-30"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        year = AcademicYear.objects.get(tenant=self.tenant_a, name="2082-2083")
        self.assertIsNotNone(year.pk)

    def test_super_admin_without_tenant_context_sees_nothing_scoped(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(reverse("academic-year-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data, [])

    def test_super_admin_can_list_users_of_a_school(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(
            reverse("user-management-list") + f"?tenant_id={self.tenant_a.tenant_id}"
        )
        self.assertEqual(response.status_code, 200, response.content)
        usernames = {row["username"] for row in response.data}
        self.assertIn("admin_a", usernames)
        self.assertIn("teacher_a", usernames)
        self.assertNotIn("admin_b", usernames)


class ReportsAccessTests(BaseTenantAPITestCase):
    """Bug E regression: /api/reports/* must resolve a tenant from the JWT."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Reports screens are feature-gated; school A holds the full-featured plan.
        cls._subscribe(cls.tenant_a)

    def test_admin_can_read_demographics(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("report-demographics"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("total_students", response.data)

    def test_admin_without_academic_year_gets_400(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("report-attendance"))
        self.assertEqual(response.status_code, 400, response.content)

    def test_reports_are_scoped_to_the_callers_tenant(self):
        AcademicYear.objects.create(
            tenant=self.tenant_a, name="2082-2083",
            start_date="2082-04-01", end_date="2083-03-30",
        )
        self.login(*self.admin_a_creds)
        year = AcademicYear.objects.get(tenant=self.tenant_a)
        response = self.client.get(reverse("report-attendance") + f"?academic_year_id={year.pk}")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["students"]["total_records"], 0)

    def test_super_admin_needs_tenant_id(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(reverse("report-demographics"))
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("No active tenant", str(response.data["message"]))

    def test_super_admin_with_tenant_id_can_read(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(
            reverse("report-demographics") + f"?tenant_id={self.tenant_a.tenant_id}"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_teacher_is_403(self):
        self.login(*self.teacher_a_creds)
        response = self.client.get(reverse("report-demographics"))
        self.assertEqual(response.status_code, 403, response.content)


class StudentCapTests(BaseTenantAPITestCase):
    """max_students is a plan limit: admission must stop at the cap."""

    def _capped_plan(self, cap=1):
        plan = Plan.objects.create(
            name="Tiny", price=0, duration_days=30, max_students=cap, is_active=True
        )
        plan.features.set(self.default_features.values())
        return plan

    def test_student_creation_stops_at_plan_cap(self):
        self._subscribe(self.tenant_a, self._capped_plan(cap=1))
        self.login(*self.admin_a_creds)

        first = self.client.post(
            reverse("student-profile-list"),
            {"user": self.student_a.pk, "roll_number": 1},
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.content)

        second = self.client.post(
            reverse("student-profile-list"),
            {"user": self.student_a.pk, "roll_number": 2},
            format="json",
        )
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn("maximum of 1 students", str(second.data))

    def test_cap_does_not_block_existing_students_above_limit(self):
        """The cap gates new admissions, not existing rows."""
        self._subscribe(self.tenant_a, self._capped_plan(cap=1))
        profile, _ = UserProfile.objects.get_or_create(
            user_account=self.student_a, defaults={"first_name": "Student"}
        )
        # Pre-existing student (count above cap) still reads/updates fine.
        Student.objects.create(
            tenant=self.tenant_a,
            user_profile=profile,
            school_class=None,
            roll_number=1,
        )
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("student-profile-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 1)

    def test_no_subscription_has_no_cap(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("student-profile-list"),
            {"user": self.student_a.pk, "roll_number": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)


class SubscriptionTests(BaseTenantAPITestCase):
    """Plan CRUD (super admin) and tenant-scoped subscription reads."""

    def test_super_admin_can_create_plan(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("plan-list"),
            {"name": "Pro", "price": "500.00", "duration_days": 180, "max_students": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["name"], "Pro")
        self.assertEqual(response.data["max_students"], 1000)

    def test_tenant_admin_cannot_create_plan(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(reverse("plan-list"), {"name": "Sneaky", "price": "1.00"}, format="json")
        self.assertEqual(response.status_code, 403, response.content)

    def test_plans_listable_by_any_authenticated_user(self):
        self.login(*self.student_a_creds)
        response = self.client.get(reverse("active-plan-list"))
        self.assertEqual(response.status_code, 200, response.content)
        # Free (price 0) comes first, then the shared "Basic" fixture plan.
        self.assertEqual([row["name"] for row in response.data], ["Free", "Basic"])

    def _subscribe_tenant_a(self):
        self.login(*self.super_admin_creds)
        return self.client.post(
            reverse("subscription-list") + f"?tenant_id={self.tenant_a.tenant_id}",
            {"plan": self.plan.pk},
            format="json",
        )

    def test_subscription_create_and_scoped_read(self):
        response = self._subscribe_tenant_a()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["plan_name"], "Basic")
        self.assertGreaterEqual(response.data["days_remaining"], 364)

        self.login(*self.admin_a_creds)
        listing = self.client.get(reverse("subscription-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]["tenant_name"], "Alpha School")
        self.assertEqual(listing.data[0]["plan_price"], "100.00")

        self.login(*self.admin_b_creds)
        listing = self.client.get(reverse("subscription-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(listing.data, [])


class LeaveWorkflowTests(BaseTenantAPITestCase):
    """Bug F regression: approve/reject are admin/HOD-only actions."""

    def _leave(self):
        return LeaveRequest.objects.create(
            tenant=self.tenant_a, teacher=self.teacher_a_profile,
            leave_type="sick", start_date="2026-09-01", end_date="2026-09-03",
            reason="Flu",
        )

    def test_teacher_can_create_own_leave_request(self):
        self.login(*self.teacher_a_creds)
        response = self.client.post(
            reverse("leave-request-list"),
            {"leave_type": "sick", "start_date": "2026-09-01", "end_date": "2026-09-03", "reason": "Flu"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        leave = LeaveRequest.objects.get(tenant=self.tenant_a)
        self.assertEqual(leave.teacher, self.teacher_a_profile)
        self.assertEqual(leave.status, "pending")

    def test_student_cannot_approve_or_reject(self):
        leave = self._leave()
        self.login(*self.student_a_creds)
        approve = self.client.post(reverse("leave-request-approve", args=[leave.pk]), format="json")
        reject = self.client.post(reverse("leave-request-reject", args=[leave.pk]), format="json")
        self.assertEqual(approve.status_code, 403, approve.content)
        self.assertEqual(reject.status_code, 403, reject.content)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")

    def test_teacher_cannot_approve_own_leave(self):
        leave = self._leave()
        self.login(*self.teacher_a_creds)
        response = self.client.post(reverse("leave-request-approve", args=[leave.pk]), format="json")
        self.assertEqual(response.status_code, 403, response.content)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")

    def test_admin_approves_leave(self):
        leave = self._leave()
        self.login(*self.admin_a_creds)
        response = self.client.post(reverse("leave-request-approve", args=[leave.pk]), format="json")
        self.assertEqual(response.status_code, 200, response.content)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")
        self.assertEqual(leave.approved_by, self.admin_a)
        self.assertIsNotNone(leave.responded_at)

    def test_admin_rejects_leave(self):
        leave = self._leave()
        self.login(*self.admin_a_creds)
        response = self.client.post(reverse("leave-request-reject", args=[leave.pk]), format="json")
        self.assertEqual(response.status_code, 200, response.content)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "rejected")
        self.assertEqual(leave.approved_by, self.admin_a)

    def test_admin_of_other_tenant_cannot_approve(self):
        leave = self._leave()
        self.login(*self.admin_b_creds)
        response = self.client.post(reverse("leave-request-approve", args=[leave.pk]), format="json")
        # The object is invisible cross-tenant (404); either way: not approved.
        self.assertIn(response.status_code, (403, 404), response.content)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")


class ParentRoleTests(BaseTenantAPITestCase):
    """The parent role reads the fee/communication/timetable screens the UI exposes.

    Note: the schema has no parent-to-student link, so the backend currently
    grants a parent the school-wide read (same simplification as `fees`). These
    tests pin what the parent UI can rely on - and that it stays read-only.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Fee/communication screens are feature-gated; school A holds the
        # full-featured plan.
        cls._subscribe(cls.tenant_a)

    def test_parent_can_read_fee_surfaces(self):
        self.login(*self.parent_a_creds)
        for url_name in [
            "student-invoice-list", "fee-payment-list",
            "fee-type-list", "fee-structure-list",
        ]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, f"{url_name}: {response.content}")

    def test_parent_can_read_communication(self):
        self.login(*self.parent_a_creds)
        for url_name in ["announcement-list", "message-list", "notification-list"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, f"{url_name}: {response.content}")

    def test_parent_can_read_timetable(self):
        self.login(*self.parent_a_creds)
        response = self.client.get(reverse("timetable-list"))
        self.assertEqual(response.status_code, 200, response.content)

    def test_parent_cannot_write_fees(self):
        self.login(*self.parent_a_creds)
        response = self.client.post(reverse("student-invoice-list"), {}, format="json")
        self.assertEqual(response.status_code, 403, response.content)

    def test_parent_cannot_manage_academics_or_users(self):
        self.login(*self.parent_a_creds)
        self.assertEqual(
            self.client.post(reverse("academic-year-list"), {}, format="json").status_code, 403
        )
        self.assertIn(
            self.client.get(reverse("user-management-list")).status_code, (403, 404)
        )


class StudentCreationTests(BaseTenantAPITestCase):
    """The student record accepts a ``user`` (UserAccount PK) write alias that
    resolves -- creating if needed -- the account's UserProfile."""

    def test_create_student_via_user_alias_links_profile(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("student-profile-list"),
            {"user": self.student_a.pk, "roll_number": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        student = Student.objects.get(tenant=self.tenant_a)
        self.assertEqual(student.user_profile.user_account, self.student_a)
        self.assertEqual(student.roll_number, 1)

    def test_user_alias_creates_missing_profile(self):
        self.assertFalse(
            UserProfile.objects.filter(user_account=self.student_a).exists()
        )
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("student-profile-list"),
            {"user": self.student_a.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        profile = UserProfile.objects.get(user_account=self.student_a)
        self.assertEqual(Student.objects.get(tenant=self.tenant_a).user_profile, profile)

    def test_unknown_user_is_400(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("student-profile-list"),
            {"user": 999999},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
