from django.contrib import admin

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


@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant')
    search_fields = ('name',)
    list_filter = ('tenant',)


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('fee_type', 'academic_year', 'school_class', 'amount', 'tenant')
    list_filter = ('academic_year', 'tenant')


@admin.register(StudentInvoice)
class StudentInvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'total_amount', 'due_date', 'status', 'tenant')
    list_filter = ('status', 'academic_year', 'tenant')
    search_fields = (
        'student__user_profile__first_name',
        'student__user_profile__last_name',
        'title',
    )


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'invoice', 'amount_paid', 'payment_method', 'payment_date', 'tenant')
    list_filter = ('payment_method', 'tenant')
    search_fields = (
        'receipt_number',
        'invoice__student__user_profile__first_name',
    )


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'amount', 'issued_at', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('receipt_number',)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'status', 'refund_date', 'tenant')
    list_filter = ('status', 'method', 'tenant')


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'discount_type', 'value', 'reason', 'tenant')
    list_filter = ('discount_type', 'tenant')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'amount', 'expense_date', 'vendor', 'tenant')
    list_filter = ('category', 'expense_date', 'tenant')
    search_fields = ('title', 'vendor')


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('staff', 'month', 'basic_salary', 'net_salary', 'status', 'tenant')
    list_filter = ('status', 'month', 'tenant')
    search_fields = ('staff__user_profile__first_name', 'staff__user_profile__last_name')