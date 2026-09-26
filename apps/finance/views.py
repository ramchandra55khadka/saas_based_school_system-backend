from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Sum

from apps.core.mixins import TenantAPIView, TenantViewSet
from apps.subscription.constants import FeatureKey
from apps.subscription.entitlements import HasFeatureAccess
from utils.permissions import (
    IsFinanceManager,
    get_membership_role,
)

from .models import (
    Discount,
    Expense,
    FeePayment,
    FeeStructure,
    FeeType,
    Payroll,
    Receipt,
    Refund,
    StudentInvoice,
)
from .serializers import (
    DiscountSerializer,
    ExpenseSerializer,
    FeePaymentSerializer,
    FeeStructureSerializer,
    FeeTypeSerializer,
    PayrollSerializer,
    ReceiptSerializer,
    RefundSerializer,
    StudentInvoiceSerializer,
)


class FinanceManageViewSet(TenantViewSet):
    """Base viewset: authenticated read, finance-office write.

    Writes are limited to the finance office — admin, principal and accountant
    (``IsFinanceManager``), the roles the frontend shows the Fees page to.
    Only schools whose plan grants the Finance feature get any access.
    """
    feature_key = FeatureKey.FINANCE

    def get_permissions(self):
        perms = [IsAuthenticated(), HasFeatureAccess()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return perms + [IsFinanceManager()]
        return perms


class FeeTypeViewSet(FinanceManageViewSet):
    """CRUD for fee types."""
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer


class FeeStructureViewSet(FinanceManageViewSet):
    """CRUD for fee structures."""
    queryset = FeeStructure.objects.select_related(
        'fee_type', 'school_class', 'academic_year'
    ).all()
    serializer_class = FeeStructureSerializer


class StudentInvoiceViewSet(FinanceManageViewSet):
    """CRUD for student invoices."""
    queryset = StudentInvoice.objects.select_related(
        'student', 'student__user_profile', 'academic_year'
    ).prefetch_related('payments').all()
    serializer_class = StudentInvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = get_membership_role(user, self.request.tenant)
        if role == 'student':
            return qs.filter(student__user_profile__user_account=user)
        if role == 'parent':
            # Parent -> student scoping lives in ``parents.StudentGuardian`` and
            # is not wired here yet; deny school-wide reads until it is.
            return qs.none()
        return qs

    def get_permissions(self):
        perms = [IsAuthenticated(), HasFeatureAccess()]
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'generate_class_invoices']:
            return perms + [IsFinanceManager()]
        return [IsAuthenticated(), HasFeatureAccess()]

    @action(detail=False, methods=['post'], url_path='generate-class-invoices')
    def generate_class_invoices(self, request):
        """Generate invoices for an entire class based on FeeStructure."""
        class_id = request.data.get('class_id')
        academic_year_id = request.data.get('academic_year_id')
        title = request.data.get('title')
        due_date = request.data.get('due_date')

        if not all([class_id, academic_year_id, title, due_date]):
            return Response(
                {"error": "class_id, academic_year_id, title, and due_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.academics.models import AcademicYear, Class

        try:
            school_class = Class.objects.get(pk=class_id, tenant=self.request.tenant)
        except Class.DoesNotExist:
            return Response({"error": "Invalid class for this school."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            academic_year = AcademicYear.objects.get(
                pk=academic_year_id, tenant=self.request.tenant
            )
        except AcademicYear.DoesNotExist:
            return Response({"error": "Invalid academic year for this school."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.students.models import Student

        students = Student.objects.filter(
            school_class=school_class, tenant=self.request.tenant
        )
        structures = FeeStructure.objects.filter(
            school_class=school_class,
            academic_year=academic_year,
            tenant=self.request.tenant,
        )

        total_amount = sum((s.amount for s in structures), Decimal('0'))
        if total_amount == 0:
            return Response(
                {"error": "No fee structure found for this class and academic year."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoices = []
        for student in students:
            inv = StudentInvoice(
                tenant=self.request.tenant,
                student=student,
                title=title,
                academic_year=academic_year,
                total_amount=total_amount,
                due_date=due_date,
            )
            # full_clean() enforces ensure_same_tenant (bulk_create skips it).
            inv.full_clean()
            invoices.append(inv)

        StudentInvoice.objects.bulk_create(invoices)
        return Response(
            {"status": "success", "message": f"Generated {len(invoices)} invoices."}
        )


class FeePaymentViewSet(FinanceManageViewSet):
    """CRUD for fee payments."""
    queryset = FeePayment.objects.select_related(
        'invoice', 'invoice__student__user_profile'
    ).all()
    serializer_class = FeePaymentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = get_membership_role(user, self.request.tenant)
        if role == 'student':
            return qs.filter(invoice__student__user_profile__user_account=user)
        if role == 'parent':
            # Same privacy constraint as StudentInvoiceViewSet.
            return qs.none()
        return qs

    def get_permissions(self):
        perms = [IsAuthenticated(), HasFeatureAccess()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return perms + [IsFinanceManager()]
        return perms


class ReceiptViewSet(FinanceManageViewSet):
    """CRUD for receipts issued against payments."""
    queryset = Receipt.objects.select_related(
        'payment', 'payment__invoice__student__user_profile'
    ).all()
    serializer_class = ReceiptSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = get_membership_role(user, self.request.tenant)
        if role == 'student':
            return qs.filter(payment__invoice__student__user_profile__user_account=user)
        if role == 'parent':
            return qs.none()
        return qs


class RefundViewSet(FinanceManageViewSet):
    """CRUD for refunds."""
    queryset = Refund.objects.select_related(
        'invoice__student__user_profile', 'payment'
    ).all()
    serializer_class = RefundSerializer


class DiscountViewSet(FinanceManageViewSet):
    """CRUD for invoice discounts."""
    queryset = Discount.objects.select_related('invoice__student__user_profile').all()
    serializer_class = DiscountSerializer


class ExpenseViewSet(FinanceManageViewSet):
    """CRUD for school expenses."""
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer


class PayrollViewSet(FinanceManageViewSet):
    """CRUD for staff payroll records."""
    queryset = Payroll.objects.select_related('staff__user_profile').all()
    serializer_class = PayrollSerializer


class FinanceReportView(TenantAPIView):
    """Financial summary: fees billed/collected/outstanding + expenses + payroll."""
    feature_key = FeatureKey.FINANCE
    permission_classes = [IsAuthenticated, HasFeatureAccess, IsFinanceManager]

    def get(self, request):
        tenant = self.require_tenant()
        year = request.query_params.get('academic_year_id')

        invoices = StudentInvoice.objects.filter(tenant=tenant)
        if year:
            invoices = invoices.filter(academic_year_id=year)

        total_billed = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
        paid = FeePayment.objects.filter(invoice__tenant=tenant).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        expenses = Expense.objects.filter(tenant=tenant).aggregate(
            total=Sum('amount')
        )['total'] or 0
        payroll = Payroll.objects.filter(tenant=tenant).aggregate(
            total=Sum('basic_salary', default=Decimal('0')) + Sum('allowances', default=Decimal('0')) - Sum('deductions', default=Decimal('0'))
        )['total'] or 0
        refunds = Refund.objects.filter(
            tenant=tenant, status='processed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        discounts = Discount.objects.filter(tenant=tenant).aggregate(
            total=Sum('value')
        )['total'] or 0

        return Response({
            "invoices": {
                "total_invoices": invoices.count(),
                "total_billed": total_billed,
                "paid": paid,
                "outstanding": total_billed - paid,
                "paid_count": invoices.filter(status='paid').count(),
                "partial_count": invoices.filter(status='partial').count(),
                "unpaid_count": invoices.filter(status='unpaid').count(),
            },
            "refunds": refunds,
            "discounts": discounts,
            "expenses": expenses,
            "payroll": payroll,
            "net_balance": paid - refunds - expenses - payroll,
        })