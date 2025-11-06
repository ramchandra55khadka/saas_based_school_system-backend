from datetime import timedelta
from django.db import models
from django.utils import timezone
from core.models import TenantModel
from tenants.models import Tenant


class Plan(models.Model):
    """Defines available subscription plans."""
    PLAN_CHOICES = [
        ('free', 'Free Plan'),
        ('basic', 'Basic Plan'),
        ('premium', 'Premium Plan'),
    ]

    plan = models.CharField(max_length=100, choices=PLAN_CHOICES, default='free')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    duration_days = models.PositiveIntegerField(default=30)  # Duration of the plan in days
    max_users = models.PositiveIntegerField(default=10)  # Max users allowed under this plan
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.get_plan_display()} - ${self.price} for {self.duration_days} days"


class Subscription(TenantModel):
    """
    One-to-one subscription per tenant (school/org).
    Auto-calculates end_date and manages is_active flag.
    """
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate end_date if not provided
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)

        # Auto-deactivate if expired
        self.is_active = self.end_date >= timezone.now()

        super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        """Return number of days remaining in the subscription."""
        return max((self.end_date - timezone.now()).days, 0) if self.end_date else 0

    @property
    def is_expired(self):
        """Check if subscription is expired."""
        return self.end_date and self.end_date < timezone.now()

    def __str__(self):
        status = "Active" if self.is_active else "Expired"
        return f"{self.tenant.tenant_name} -> {self.get_plan_display()} ({status})"
