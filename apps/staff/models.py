from django.db import models

from apps.core.models import ensure_same_tenant, AbstractTenantModel
from apps.tenants.models import Department
from apps.user_profile.models import UserProfile
from utils.abstract_model import AbstractTimeStampedModel
from .constants import (
    DESIGNATION_ALLOWED_ROLES,
    DESIGNATION_CHOICES,
    DESIGNATION_DEFAULT,
    QUALIFICATION_CHOICES,
    QUALIFICATION_MAX_LENGTH,
)


class Staff(AbstractTenantModel, AbstractTimeStampedModel):
    """School staff profile for teachers, librarians, principals, and other staff."""
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="staff",
    )
    designation = models.CharField(
        max_length=30,
        choices=DESIGNATION_CHOICES,
        default=DESIGNATION_DEFAULT,
    )
    employee_id = models.CharField(max_length=50, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_members',
    )
    qualification = models.CharField(
        max_length=QUALIFICATION_MAX_LENGTH,
        choices=QUALIFICATION_CHOICES,
        blank=True,
    )
    specialization = models.CharField(max_length=200, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['user_profile__first_name']
        verbose_name = 'Staff'
        verbose_name_plural = 'Staff'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'employee_id'],
                name='unique_staff_employee_per_school',
                condition=~models.Q(employee_id=''),
            )
        ]
        indexes = [
            models.Index(fields=['tenant', 'designation', 'is_active']),
            models.Index(fields=['tenant', 'department', 'is_active']),
        ]

    def __str__(self):
        return f'{self.user_profile} ({self.get_designation_display()})'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'department')
        allowed_roles = DESIGNATION_ALLOWED_ROLES[self.designation]
        if (
            self.user_profile_id
            and self.tenant_id
            and not self.user_profile.user_account.memberships.filter(
                tenant=self.tenant,
                is_active=True,
                role__in=allowed_roles,
            ).exists()
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({'user_profile': 'Account role does not match this staff designation for the school.'})
