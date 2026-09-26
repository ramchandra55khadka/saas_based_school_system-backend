from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DiscountViewSet,
    ExpenseViewSet,
    FeePaymentViewSet,
    FeeStructureViewSet,
    FeeTypeViewSet,
    FinanceReportView,
    PayrollViewSet,
    ReceiptViewSet,
    RefundViewSet,
    StudentInvoiceViewSet,
)

router = DefaultRouter()
router.register(r'fee-types', FeeTypeViewSet, basename='fee-type')
router.register(r'fee-structures', FeeStructureViewSet, basename='fee-structure')
router.register(r'invoices', StudentInvoiceViewSet, basename='student-invoice')
router.register(r'payments', FeePaymentViewSet, basename='fee-payment')
router.register(r'receipts', ReceiptViewSet, basename='receipt')
router.register(r'refunds', RefundViewSet, basename='refund')
router.register(r'discounts', DiscountViewSet, basename='discount')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'payroll', PayrollViewSet, basename='payroll')

urlpatterns = [
    path('', include(router.urls)),
    path('report/', FinanceReportView.as_view(), name='finance-report'),
]