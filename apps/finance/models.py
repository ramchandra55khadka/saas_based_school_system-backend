import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from decimal import Decimal

from apps.academics.models import AcademicYear, Class
from apps.core.models import AbstractTenantModel, ensure_same_tenant
from apps.staff.models import Staff
from apps.students.models import Student
from utils.abstract_model import AbstractTimeStampedModel

from .constants import (
    DEFAULT_DISCOUNT_TYPE,
    DEFAULT_PAYMENT_METHOD,
    EXPENSE_CATEGORY_CHOICES,
    EXPENSE_CATEGORY_OTHER,
    INVOICE_DEFAULT_STATUS,
    InvoiceStatus,
    PAYMENT_CASH,
    PAYROLL_DEFAULT_STATUS,
    PayrollStatus,
    PaymentMethod,
    RECEIPT_NUMBER_LENGTH,
    RECEIPT_NUMBER_PREFIX,
    REFUND_DEFAULT_STATUS,
    RefundStatus,
    REFUND_METHOD_CHOICES,
    DiscountType,
)


class FeeType(AbstractTenantModel, AbstractTimeStampedModel):
    """A kind of fee (e.g. Tuition Fee, Transport Fee)."""
    name = models.CharField(max_length=100, help_text="e.g. Tuition Fee, Transport Fee")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        unique_together = ('tenant', 'name')
        verbose_name = 'Fee Type'
        verbose_name_plural = 'Fee Types'

    def __str__(self):
        return f"{self.name} ({self.tenant.tenant_name})"


class FeeStructure(AbstractTenantModel, AbstractTimeStampedModel):
    """The amount charged for a fee type in a class, for an academic year."""
    fee_type = models.ForeignKey(FeeType, on_delete=models.CASCADE, related_name='structures')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='fee_structures')
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='fee_structures')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['academic_year', 'school_class', 'fee_type']
        unique_together = ('fee_type', 'academic_year', 'school_class')
        verbose_name = 'Fee Structure'
        verbose_name_plural = 'Fee Structures'

    def __str__(self):
        return f"{self.fee_type.name} - {self.school_class.name} - {self.amount}"

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'fee_type', 'academic_year', 'school_class')


class StudentInvoice(AbstractTenantModel, AbstractTimeStampedModel):
    """A bill issued to a student for a set of fees in an academic year."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='invoices')
    title = models.CharField(max_length=200, help_text="e.g. Term 1 Fees")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='invoices')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=INVOICE_DEFAULT_STATUS,
    )

    class Meta:
        ordering = ['-due_date']
        verbose_name = 'Student Invoice'
        verbose_name_plural = 'Student Invoices'

    def __str__(self):
        return f"Invoice {self.title} for {self.student.user_profile} ({self.status})"

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'student', 'academic_year')

    @property
    def amount_paid(self):
        total = self.payments.aggregate(total=Sum('amount_paid'))['total']
        return total or 0

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid


class FeePayment(AbstractTenantModel, AbstractTimeStampedModel):
    """A payment made towards an invoice (a receipt is generated from it)."""
    invoice = models.ForeignKey(StudentInvoice, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    payment_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=DEFAULT_PAYMENT_METHOD,
    )
    receipt_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="Reference ID for bank/online payments")
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Fee Payment'
        verbose_name_plural = 'Fee Payments'

    def save(self, *args, **kwargs):
        if self.invoice_id and not self.tenant_id:
            self.tenant = self.invoice.tenant
        if not self.receipt_number:
            self.receipt_number = f"{RECEIPT_NUMBER_PREFIX}{uuid.uuid4().hex[:RECEIPT_NUMBER_LENGTH].upper()}"
        super().save(*args, **kwargs)
        self._sync_invoice_status(self.invoice)

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        self._sync_invoice_status(invoice)

    @staticmethod
    def _sync_invoice_status(invoice):
        """Recompute the invoice's status from its (remaining) payments."""
        paid = invoice.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
        if paid <= 0:
            invoice.status = INVOICE_DEFAULT_STATUS
        elif paid >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.PARTIAL
        if invoice.pk:
            invoice.save(update_fields=['status'])

    def __str__(self):
        return f"Receipt {self.receipt_number} for {self.invoice.student.user_profile} - {self.amount_paid}"

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'invoice')


class Receipt(AbstractTenantModel, AbstractTimeStampedModel):
    """An official receipt document issued for a payment."""
    receipt_number = models.CharField(max_length=50, blank=True)
    payment = models.OneToOneField(
        FeePayment, on_delete=models.CASCADE, related_name='receipt'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='receipts_issued',
    )
    issued_at = models.DateField(auto_now_add=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']
        unique_together = ('tenant', 'receipt_number')
        verbose_name = 'Receipt'
        verbose_name_plural = 'Receipts'

    def save(self, *args, **kwargs):
        if not self.amount:
            self.amount = self.payment.amount_paid
        if not self.receipt_number:
            self.receipt_number = f"{RECEIPT_NUMBER_PREFIX}{uuid.uuid4().hex[:RECEIPT_NUMBER_LENGTH].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receipt {self.receipt_number} for {self.payment}"

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'payment')


class Refund(AbstractTenantModel, AbstractTimeStampedModel):
    """Money returned to a student (against an invoice or a specific payment)."""
    invoice = models.ForeignKey(
        StudentInvoice, on_delete=models.CASCADE, related_name='refunds'
    )
    payment = models.ForeignKey(
        FeePayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=REFUND_METHOD_CHOICES, default=PAYMENT_CASH)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=REFUND_DEFAULT_STATUS,
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds_processed',
    )
    refund_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'

    def __str__(self):
        return f"Refund {self.amount} for {self.invoice}"

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'invoice', 'payment')


class Discount(AbstractTenantModel, AbstractTimeStampedModel):
    """A discount applied to an invoice (fixed amount or percentage)."""
    invoice = models.ForeignKey(
        StudentInvoice, on_delete=models.CASCADE, related_name='discounts'
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DEFAULT_DISCOUNT_TYPE,
    )
    value = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discounts_approved',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Discount'
        verbose_name_plural = 'Discounts'

    def __str__(self):
        suffix = '%' if self.discount_type == DiscountType.PERCENTAGE else ''
        return f"Discount {self.value}{suffix} on {self.invoice}"

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'invoice')
        if self.discount_type == DiscountType.PERCENTAGE and not 0 <= self.value <= 100:
            from django.core.exceptions import ValidationError
            raise ValidationError({'value': 'Percentage discount must be between 0 and 100.'})


class Expense(AbstractTenantModel, AbstractTimeStampedModel):
    """An expense incurred by the school."""
    category = models.CharField(
        max_length=30,
        choices=EXPENSE_CATEGORY_CHOICES,
        default=EXPENSE_CATEGORY_OTHER,
    )
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    vendor = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=DEFAULT_PAYMENT_METHOD,
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses_recorded',
    )

    class Meta:
        ordering = ['-expense_date']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"{self.title} ({self.amount})"


class Payroll(AbstractTenantModel, AbstractTimeStampedModel):
    """Monthly payroll record for a staff member."""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='payroll_records')
    month = models.DateField(help_text="First day of the payroll month, e.g. 2026-01-01")
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=PayrollStatus.choices,
        default=PAYROLL_DEFAULT_STATUS,
    )
    payment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-month']
        unique_together = ('tenant', 'staff', 'month')
        verbose_name = 'Payroll Record'
        verbose_name_plural = 'Payroll Records'

    def __str__(self):
        return f"{self.staff.user_profile} - {self.month} - {self.net_salary}"

    @property
    def gross_salary(self):
        return self.basic_salary + self.allowances

    @property
    def net_salary(self):
        return self.basic_salary + self.allowances - self.deductions

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'staff')