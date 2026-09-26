"""Fee-type / fee-structure management tests for the Fees page.

``manage_fees`` in the frontend shows the Fees page to admin, principal and
accountant, so all three must be able to manage what it exposes — that is what
``IsFinanceManager`` grants. Teachers and students keep read access only, and
the whole area is additionally gated on the plan's ``finance`` feature.
"""
from decimal import Decimal

from django.urls import reverse

from apps.academics.models import AcademicYear, Class
from apps.core.tests import BaseTenantAPITestCase
from apps.finance.models import FeeStructure, FeeType
from apps.user_account.models import RoleChoices, TenantMembership, UserAccount


class FeeTypeManagementTests(BaseTenantAPITestCase):
    """``/api/finance/fee-types/`` — behind the "Add fee type" dialog."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.accountant_a = UserAccount.objects.create_user(
            username="accountant_a",
            password="accountant-a-pass-123",
            email="accountant_a@example.com",
        )
        TenantMembership.objects.create(
            user=cls.accountant_a, tenant=cls.tenant_a, role=RoleChoices.ACCOUNTANT
        )
        cls.accountant_a_creds = ("accountant_a", "accountant-a-pass-123")
        # The shared plan grants every feature, so school A has finance.
        cls._subscribe(cls.tenant_a)

    def test_admin_creates_a_fee_type(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("fee-type-list"), {"name": "Tuition Fee"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        fee_type = FeeType.objects.get(name="Tuition Fee")
        self.assertEqual(fee_type.tenant, self.tenant_a)
        # `tenant` is implied by the active school, never sent by the client.
        self.assertEqual(response.data["tenant"], self.tenant_a.pk)

    def test_accountant_creates_and_lists_fee_types(self):
        self.login(*self.accountant_a_creds)
        created = self.client.post(
            reverse("fee-type-list"),
            {"name": "Transport Fee", "description": "Monthly bus fare"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)

        listing = self.client.get(reverse("fee-type-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual([row["name"] for row in listing.data], ["Transport Fee"])

    def test_duplicate_name_is_a_clean_400(self):
        FeeType.objects.create(tenant=self.tenant_a, name="Tuition Fee")
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("fee-type-list"), {"name": "tuition fee"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("name", response.data)
        self.assertEqual(FeeType.objects.filter(tenant=self.tenant_a).count(), 1)

    def test_admin_can_edit_and_delete_a_fee_type(self):
        fee_type = FeeType.objects.create(tenant=self.tenant_a, name="Tuition Fee")
        self.login(*self.admin_a_creds)

        update = self.client.patch(
            reverse("fee-type-detail", args=[fee_type.pk]),
            {"name": "Tuition", "description": "Term fee"},
            format="json",
        )
        self.assertEqual(update.status_code, 200, update.content)
        fee_type.refresh_from_db()
        self.assertEqual(fee_type.name, "Tuition")
        self.assertEqual(fee_type.description, "Term fee")

        delete = self.client.delete(reverse("fee-type-detail", args=[fee_type.pk]))
        self.assertEqual(delete.status_code, 204, delete.content)
        self.assertFalse(FeeType.objects.filter(pk=fee_type.pk).exists())

    def test_teacher_cannot_write_but_can_read(self):
        FeeType.objects.create(tenant=self.tenant_a, name="Tuition Fee")
        self.login(*self.teacher_a_creds)
        denied = self.client.post(
            reverse("fee-type-list"), {"name": "Exam Fee"}, format="json"
        )
        self.assertEqual(denied.status_code, 403, denied.content)
        self.assertFalse(FeeType.objects.filter(name="Exam Fee").exists())

        listing = self.client.get(reverse("fee-type-list"))
        self.assertEqual(listing.status_code, 200, listing.content)

    def test_fee_types_are_tenant_scoped(self):
        FeeType.objects.create(tenant=self.tenant_b, name="Beta Only")
        self.login(*self.admin_a_creds)
        listing = self.client.get(reverse("fee-type-list"))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual([row["name"] for row in listing.data], [])

    def test_plan_without_finance_blocks_everything(self):
        # School B has no subscription, so its plan grants no finance feature.
        self.login(*self.admin_b_creds)
        self.assertEqual(self.client.get(reverse("fee-type-list")).status_code, 403)
        blocked = self.client.post(
            reverse("fee-type-list"), {"name": "Tuition Fee"}, format="json"
        )
        self.assertEqual(blocked.status_code, 403, blocked.content)
        self.assertFalse(FeeType.objects.filter(tenant=self.tenant_b).exists())

    def test_anonymous_is_401(self):
        self.assertEqual(self.client.get(reverse("fee-type-list")).status_code, 401)


class FeeStructureManagementTests(BaseTenantAPITestCase):
    """``/api/finance/fee-structures/`` — a fee type priced per class + year."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.accountant_a = UserAccount.objects.create_user(
            username="accountant_a",
            password="accountant-a-pass-123",
            email="accountant_a@example.com",
        )
        TenantMembership.objects.create(
            user=cls.accountant_a, tenant=cls.tenant_a, role=RoleChoices.ACCOUNTANT
        )
        cls.accountant_a_creds = ("accountant_a", "accountant-a-pass-123")
        cls._subscribe(cls.tenant_a)
        cls.year = AcademicYear.objects.create(
            tenant=cls.tenant_a,
            name="2082-2083",
            start_date="2082-04-01",
            end_date="2083-03-30",
            is_current=True,
        )
        cls.grade_10 = Class.objects.create(
            tenant=cls.tenant_a, name="Grade 10", numeric_name=10
        )
        cls.fee_type = FeeType.objects.create(
            tenant=cls.tenant_a, name="Tuition Fee"
        )

    def _payload(self, **overrides):
        payload = {
            "fee_type": self.fee_type.pk,
            "academic_year": self.year.pk,
            "school_class": self.grade_10.pk,
            "amount": "2500.00",
        }
        payload.update(overrides)
        return payload

    def test_accountant_can_create_a_fee_structure(self):
        self.login(*self.accountant_a_creds)
        response = self.client.post(
            reverse("fee-structure-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

        structure = FeeStructure.objects.get()
        self.assertEqual(structure.tenant, self.tenant_a)
        self.assertEqual(structure.amount, Decimal("2500.00"))
        # Enriched fields the table renders.
        self.assertEqual(response.data["fee_type_name"], "Tuition Fee")
        self.assertEqual(response.data["class_name"], "Grade 10")

    def test_duplicate_structure_is_a_clean_400(self):
        FeeStructure.objects.create(
            tenant=self.tenant_a,
            fee_type=self.fee_type,
            academic_year=self.year,
            school_class=self.grade_10,
            amount=Decimal("1000.00"),
        )
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("fee-structure-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(FeeStructure.objects.count(), 1)

    def test_teacher_cannot_create_a_fee_structure(self):
        self.login(*self.teacher_a_creds)
        response = self.client.post(
            reverse("fee-structure-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(FeeStructure.objects.exists())