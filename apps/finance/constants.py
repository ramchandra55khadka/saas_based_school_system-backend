"""finance app constants."""
from django.db import models


# --- StudentInvoice.status ------------------------------------------------------
class InvoiceStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PARTIAL = 'partial', 'Partial'
    PAID = 'paid', 'Paid'


INVOICE_UNPAID = InvoiceStatus.UNPAID
INVOICE_PARTIAL = InvoiceStatus.PARTIAL
INVOICE_PAID = InvoiceStatus.PAID
INVOICE_DEFAULT_STATUS = InvoiceStatus.UNPAID

# --- FeePayment.payment_method --------------------------------------------------
class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
    CHEQUE = 'cheque', 'Cheque'
    ONLINE = 'online', 'Online'


PAYMENT_CASH = PaymentMethod.CASH
PAYMENT_BANK_TRANSFER = PaymentMethod.BANK_TRANSFER
PAYMENT_CHEQUE = PaymentMethod.CHEQUE
PAYMENT_ONLINE = PaymentMethod.ONLINE
DEFAULT_PAYMENT_METHOD = PaymentMethod.CASH

# --- Receipt --------------------------------------------------------------------
# FeePayment.save() mints "REC-XXXXXXXX" from a uuid4 hex when no receipt
# number is supplied; Receipt reuses the same scheme for its own number.
RECEIPT_NUMBER_PREFIX = 'REC-'
RECEIPT_NUMBER_LENGTH = 8

# --- Refund ---------------------------------------------------------------------
class RefundStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSED = 'processed', 'Processed'
    DECLINED = 'declined', 'Declined'


REFUND_PENDING = RefundStatus.PENDING
REFUND_PROCESSED = RefundStatus.PROCESSED
REFUND_DECLINED = RefundStatus.DECLINED
REFUND_DEFAULT_STATUS = RefundStatus.PENDING
REFUND_METHOD_CHOICES = [
    ('cash', 'Cash'),
    ('bank_transfer', 'Bank Transfer'),
    ('cheque', 'Cheque'),
    ('online', 'Online'),
]

# --- Discount -------------------------------------------------------------------
class DiscountType(models.TextChoices):
    FIXED = 'fixed', 'Fixed Amount'
    PERCENTAGE = 'percentage', 'Percentage'


DISCOUNT_FIXED = DiscountType.FIXED
DISCOUNT_PERCENTAGE = DiscountType.PERCENTAGE
DEFAULT_DISCOUNT_TYPE = DiscountType.FIXED

# --- Expense.category ------------------------------------------------------------
EXPENSE_CATEGORY_CHOICES = [
    ('salary', 'Salaries'),
    ('rent', 'Rent'),
    ('utilities', 'Utilities'),
    ('maintenance', 'Maintenance'),
    ('supplies', 'Supplies & Materials'),
    ('transport', 'Transport'),
    ('events', 'Events & Activities'),
    ('other', 'Other'),
]
EXPENSE_CATEGORY_OTHER = 'other'

# --- Payroll.status --------------------------------------------------------------
class PayrollStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'


PAYROLL_PENDING = PayrollStatus.PENDING
PAYROLL_PAID = PayrollStatus.PAID
PAYROLL_DEFAULT_STATUS = PayrollStatus.PENDING