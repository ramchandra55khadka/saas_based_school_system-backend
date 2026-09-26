from django.conf import settings
from django.db import models
from django.utils.timezone import now
from apps.tenants.models import Tenant

from utils.abstract_model import AbstractTimeStampedModel, AbstractUUID
from .constants import (
    DEFAULT_PLAN_DURATION_DAYS,
    DEFAULT_PLAN_MAX_STUDENTS,
    FeatureKey,
    SubscriptionRequestStatus,
    SubscriptionRequestType,
)


class Feature(AbstractUUID, AbstractTimeStampedModel, models.Model):
    """A functional capability a Plan can grant (e.g. Library, Finance).

    Plans link to Features through a many-to-many, so entitlement checks ask
    ``has_feature(tenant, "finance")`` instead of comparing plan names.
    """
    key = models.CharField(
        max_length=50, unique=True, choices=FeatureKey.choices,
        help_text="Stable machine identifier, e.g. 'finance'.",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Feature'
        verbose_name_plural = 'Features'

    def __str__(self):
        return self.name


class Plan(AbstractUUID, AbstractTimeStampedModel, models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=DEFAULT_PLAN_DURATION_DAYS)
    max_students = models.PositiveIntegerField(
        default=DEFAULT_PLAN_MAX_STUDENTS,
        help_text="Maximum students this plan allows (a limit, not a feature).",
    )
    features = models.ManyToManyField(
        Feature, related_name='plans', blank=True,
        help_text="Features this plan grants its subscribers.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['price', 'name']

    def __str__(self):
        return self.name

    def feature_keys(self):
        """Effective feature keys for this plan, as a set of strings."""
        return set(self.features.filter(is_active=True).values_list('key', flat=True))


class Subscription(AbstractUUID, models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['plan', 'is_active']),
        ]

    def __str__(self):
        return f"{self.tenant.tenant_name} - {self.plan.name}"

    @property
    def days_remaining(self):
        from django.utils import timezone
        delta = self.end_date - timezone.now()
        return max(0, delta.days)


class SubscriptionRequest(AbstractUUID, AbstractTimeStampedModel, models.Model):
    """A school's request to renew / change its subscription plan.

    The school cannot touch its live subscription directly — it submits a
    request, and a platform super admin approves or rejects it. Approving
    applies the change through the same ``services`` the admin UI uses, so
    renewal/upgrade payments are recorded exactly once.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='subscription_requests'
    )
    request_type = models.CharField(
        max_length=20, choices=SubscriptionRequestType.choices,
        help_text="What the school is asking for: renew the current plan or switch plan.",
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, null=True, blank=True,
        help_text="Target plan for a change-plan request (renew keeps the current plan).",
    )
    message = models.TextField(
        blank=True, help_text="Optional note from the school to the platform admin."
    )
    status = models.CharField(
        max_length=20, choices=SubscriptionRequestStatus.choices,
        default=SubscriptionRequestStatus.PENDING, db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subscription_requests',
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='processed_subscription_requests',
        help_text="Super admin who approved or rejected this request.",
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(
        blank=True, help_text="Reply from the platform admin, e.g. rejection reason."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Subscription Request'
        verbose_name_plural = 'Subscription Requests'
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.tenant.tenant_name} - {self.get_request_type_display()} ({self.get_status_display()})"


class PaymentStatus(models.TextChoices):
    PAID = 'paid', 'Paid'
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class PaymentMethod(models.TextChoices):
    ONLINE = 'online', 'Online'
    BANK = 'bank', 'Bank Transfer'
    CARD = 'card', 'Card'
    CASH = 'cash', 'Cash'


class SubscriptionPayment(AbstractUUID, AbstractTimeStampedModel, models.Model):
    """An order/payment a school makes for its subscription.

    ``amount`` is snapshotted at payment time so historical revenue stays
    accurate even if the plan's price changes later. A subscription's first
    payment is its initial order; renewals/upgrades are recorded with
    ``is_renewal=True``. Revenue analytics count only ``status='paid'`` rows.
    """
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='payments'
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name='payments',
        help_text="Plan this payment was charged for (price snapshot).",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAID
    )
    method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.ONLINE
    )
    reference = models.CharField(
        max_length=100, blank=True,
        help_text="Bank/online order reference for this payment.",
    )
    payment_date = models.DateTimeField(default=now, db_index=True)
    is_renewal = models.BooleanField(
        default=False,
        help_text="True when this payment renewed or upgraded an existing subscription.",
    )

    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Subscription Payment'
        verbose_name_plural = 'Subscription Payments'
        indexes = [
            models.Index(fields=['status', 'payment_date']),
            models.Index(fields=['subscription', 'is_renewal']),
        ]

    def __str__(self):
        return (
            f"{self.subscription.tenant.tenant_name} - {self.plan.name} "
            f"({self.amount})"
        )