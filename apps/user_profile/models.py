"""Common personal information for an authenticated user account.

``UserProfile`` is the single place a person's identity lives — name, phone,
date of birth, address and photo — regardless of which school role they hold.
Role-specific, tenant-scoped records are separate models in their own apps and
hang off this profile:

* ``students.Student``   — class, section, roll number (``profile.student``)
* ``parents.Parent``     — occupation, emergency contact (``profile.parent``)
* ``staff.Staff`` — employment details (``profile.staff``)
"""
from django.db import models

from apps.user_account.models import UserAccount
from utils.abstract_model import AbstractTimeStampedModel, AbstractUUID

from .constants import GENDER_CHOICES, GENDER_MAX_LENGTH, NATIONALITY_MAX_LENGTH


class UserProfile(AbstractUUID, AbstractTimeStampedModel, models.Model):
    """Common personal information for an authenticated user account."""
    user_account = models.OneToOneField(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(
        max_length=GENDER_MAX_LENGTH,
        choices=GENDER_CHOICES,
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=NATIONALITY_MAX_LENGTH, blank=True)
    address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)

    class Meta:
        ordering = ['first_name', 'last_name']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.user_account.username
