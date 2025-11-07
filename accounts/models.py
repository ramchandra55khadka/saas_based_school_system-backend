from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from tenants.models import Tenant

# ---------------------------
# ROLE CHOICES
# ---------------------------
class RoleChoices(models.TextChoices):
    SUPER_ADMIN = 'super-admin', 'Super Admin'
    ADMIN = 'admin', 'Admin'
    HOD = 'hod', 'Head of Department'
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'


# ---------------------------
# CUSTOM USER MODEL
# ---------------------------
class User(AbstractUser):
    """
    Shared user model for all tenants.
    Super Admins are global (no tenant link).
    Tenant members connect via TenantMembership.
    """
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=300, unique=True)
    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=30,
        choices=RoleChoices.choices,
        default=RoleChoices.STUDENT
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    # -------- Role helper methods --------
    def is_super_admin(self):
        return self.role == RoleChoices.SUPER_ADMIN

    def is_admin(self):
        return self.role == RoleChoices.ADMIN

    def is_hod(self):
        return self.role == RoleChoices.HOD

    def is_teacher(self):
        return self.role == RoleChoices.TEACHER

    def is_student(self):
        return self.role == RoleChoices.STUDENT

    # -------- Validation --------
    def clean(self):
        # Admins must belong to a tenant
        if self.role == RoleChoices.ADMIN and not hasattr(self, 'tenant'):
            raise ValidationError("Admin must belong to a tenant (organization).")

        # Super admins must NOT belong to any tenant
        if self.role == RoleChoices.SUPER_ADMIN and hasattr(self, 'tenant') and self.tenant:
            raise ValidationError("Super Admin cannot belong to a tenant.")


# ---------------------------
# TENANT MEMBERSHIP
# ---------------------------
class TenantMembership(models.Model):
    """
    Defines user's membership within a tenant (organization).
    Enables multi-tenant participation.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="memberships"
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(
        max_length=30,
        choices=RoleChoices.choices
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'tenant')

    def __str__(self):
        return f"{self.user} in {self.tenant} as {self.role}"
