from django.db import models
from django.utils import timezone
from accounts.models import Organization

class Plan(models.Model):
    """Defines available subscription plans.""" 
    plan_choices = [
        ('free', 'Free Plan'),
        ('basic', 'Basic Plan'),
        ('premium', 'Premium Plan'),
    ]
    plan = models.CharField(max_length=100, choices=plan_choices,default='free') 
    description = models.TextField()
    price=models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    duration_days = models.PositiveIntegerField(default=30)  # Duration of the plan in days
    max_users = models.PositiveIntegerField(default=10)  # Max users allowed under this plan
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return f"{self.plan} - ${self.price} for {self.duration_days} days"
    

class Subscription(models.Model): 
    """Tracks organization subscriptions to plans."""

    organization=models.OneToOneField(Organization,on_delete=models.CASCADE,related_name='subscription')
    # The Purpose of models.OneToOneField
    # The OneToOneField is the most restrictive relationship field in Django. It means:

    # Unique Constraint: Every Organization instance can be related to at most one Subscription instance.

    # Referential Integrity: If you delete the Organization, the related Subscription is also deleted (due to on_delete=models.CASCADE).
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # auto calculate end_date if not provided
        if not self.end_date:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)

        #auto deactivate if end_date has passed
        if self.end_date < timezone.now():
            self.is_active = False
        super().save(*args, **kwargs)

    
    def __str__(self):
        return f"{self.organization.org_name} -> {self.plan.plan} "
    
    @property
    def days_remaining(self): 
        """Return number of days remaining in the subscription.(days remain until expiry)"""
        return max((self.end_date - timezone.now()).days, 0)