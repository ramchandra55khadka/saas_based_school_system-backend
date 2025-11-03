from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# --------------------------------
# Organization Model
# --------------------------------
class Organization(models.Model):
    org_name = models.CharField(max_length=255, unique=True,blank=False)
    org_reg_no = models.CharField(max_length=100, unique=True,blank=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.org_name


# --------------------------------
# Custom User Model
# --------------------------------
class User(AbstractUser):
    """
    Custom user linked to an organization (tenant-based model).
    Includes roles: super-admin, admin, hod, teacher, student.
    """

    ROLE_CHOICES = [
        ('super-admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('hod', 'Head of Department'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} ({self.role})"

    class Meta:
        ordering = ["id"]
