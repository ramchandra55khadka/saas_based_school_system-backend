"""Parent/guardian models.

``Parent`` and ``StudentGuardian`` used to live in ``user_profile`` alongside
``UserProfile``. They are tenant-scoped school data (a parent belongs to one
school, and guardianship links a student to a parent *within* that school), so
they live in their own app now — ``user_profile`` keeps only the personal
information that hangs off an authenticated account.

``Student`` itself lives in the ``students`` app; this app imports it directly
(the dependency is one-way, so there is no import cycle).
"""
from django.db import models

from apps.core.models import ensure_same_tenant, AbstractTenantModel
from apps.students.models import Student
from apps.user_profile.models import UserProfile
from utils.abstract_model import AbstractTimeStampedModel

from .constants import (
    GUARDIAN_RELATION_CHOICES,
    PARENT_REQUIRED_ROLE,
)


class Parent(AbstractTenantModel, AbstractTimeStampedModel):
    """Parent or guardian profile linked to a user profile."""
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='parent',
    )
    occupation = models.CharField(max_length=100, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['user_profile__first_name']
        verbose_name = 'Parent'
        verbose_name_plural = 'Parents'

    def __str__(self):
        return str(self.user_profile)

    def clean(self):
        super().clean()
        if (
            self.user_profile_id
            and self.tenant_id
            and not self.user_profile.user_account.memberships.filter(
                tenant=self.tenant,
                is_active=True,
                role=PARENT_REQUIRED_ROLE,
            ).exists()
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({'user_profile': 'Account must have an active parent membership in this school.'})


class StudentGuardian(AbstractTenantModel, AbstractTimeStampedModel):
    """Connects students with parent/guardian profiles."""
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='guardians',
    )
    parent = models.ForeignKey(
        Parent,
        on_delete=models.CASCADE,
        related_name='wards',
    )
    relation = models.CharField(max_length=30, choices=GUARDIAN_RELATION_CHOICES)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['student', '-is_primary']
        verbose_name = 'Student Guardian'
        verbose_name_plural = 'Student Guardians'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'parent'],
                name='unique_student_guardian',
            )
        ]

    def __str__(self):
        return f'{self.parent} -> {self.student} ({self.get_relation_display()})'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'student', 'parent')
