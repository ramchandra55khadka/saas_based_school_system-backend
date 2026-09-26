from rest_framework import serializers

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


class FeeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeType
        fields = ['id', 'tenant', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_name(self, value):
        """``unique_together = ('tenant', 'name')`` as a form error, not a 500.

        ``tenant`` is injected by the viewset (it is not a writable serializer
        field), so DRF cannot build a unique-together validator and the
        constraint would only blow up at INSERT time.
        """
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant is None:
            return value
        duplicates = FeeType.objects.filter(tenant=tenant, name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                'This fee type already exists in this school.'
            )
        return value


class FeeStructureSerializer(serializers.ModelSerializer):
    fee_type_name = serializers.CharField(source='fee_type.name', read_only=True)
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            'id', 'tenant', 'fee_type', 'fee_type_name',
            'academic_year', 'academic_year_name',
            'school_class', 'class_name',
            'amount', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class FeePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeePayment
        fields = [
            'id', 'tenant', 'invoice', 'amount_paid', 'payment_date',
            'payment_method', 'receipt_number', 'transaction_id', 'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'receipt_number', 'created_at', 'updated_at']


class StudentInvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user_profile', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payments = FeePaymentSerializer(many=True, read_only=True)

    class Meta:
        model = StudentInvoice
        fields = [
            'id', 'tenant', 'student', 'student_name', 'title',
            'academic_year', 'academic_year_name', 'total_amount',
            'due_date', 'status', 'amount_paid', 'balance_due', 'payments',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'status', 'created_at', 'updated_at']


class ReceiptSerializer(serializers.ModelSerializer):
    payment_invoice = serializers.CharField(source='payment.invoice', read_only=True)
    student_name = serializers.CharField(
        source='payment.invoice.student.user_profile', read_only=True
    )

    class Meta:
        model = Receipt
        fields = [
            'id', 'tenant', 'receipt_number', 'payment', 'payment_invoice',
            'student_name', 'amount', 'issued_by', 'issued_at', 'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'receipt_number', 'issued_at', 'created_at', 'updated_at']


class RefundSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source='invoice.student.user_profile', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        model = Refund
        fields = [
            'id', 'tenant', 'invoice', 'payment', 'student_name',
            'amount', 'method', 'reason', 'status', 'status_display',
            'processed_by', 'refund_date', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class DiscountSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source='invoice.student.user_profile', read_only=True
    )
    discount_type_display = serializers.CharField(
        source='get_discount_type_display', read_only=True
    )

    class Meta:
        model = Discount
        fields = [
            'id', 'tenant', 'invoice', 'student_name',
            'discount_type', 'discount_type_display', 'value', 'reason',
            'approved_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(
        source='get_category_display', read_only=True
    )
    method_display = serializers.CharField(
        source='get_payment_method_display', read_only=True
    )

    class Meta:
        model = Expense
        fields = [
            'id', 'tenant', 'category', 'category_display', 'title', 'amount',
            'expense_date', 'vendor', 'payment_method', 'method_display',
            'notes', 'recorded_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class PayrollSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user_profile', read_only=True)
    gross_salary = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    net_salary = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        model = Payroll
        fields = [
            'id', 'tenant', 'staff', 'staff_name', 'month',
            'basic_salary', 'allowances', 'deductions',
            'gross_salary', 'net_salary', 'status', 'status_display',
            'payment_date', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']