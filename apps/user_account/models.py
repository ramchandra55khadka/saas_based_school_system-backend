import uuid

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.tenants.models import Tenant

from utils.abstract_model import AbstractUUID
from .managers import UserAccountManager

# Re-exported so ``from user_account.models import RoleChoices`` keeps working;
# the single source of truth lives in constants.py.
from .constants import ROLE_MAX_LENGTH, RoleChoices  # noqa: F401


class UserAccount(AbstractBaseUser, PermissionsMixin):
    """Authentication account shared across all schools.

    Identity + login state only: personal details (first/last name, date of
    birth, address, …) live on the linked ``user_profile.UserProfile`` row
    (``user.profile``), so this model deliberately does not re-declare them.
    """

    # Stable public identifier, distinct from the auto integer PK.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, unique=True)

    username = models.CharField(max_length=300, unique=True)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    # Contact-verification flags. Flipped by the verification flows (the API
    # exposes them read-only — never by ordinary edits).
    email_is_verified = models.BooleanField(default=False)
    phone_is_verified = models.BooleanField(default=False)

    objects = UserAccountManager()
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['username']
        verbose_name = 'User Account'
        verbose_name_plural = 'User Accounts'

    def __str__(self):
        return self.username

    def is_super_admin(self):
        return self.is_superuser

    def role_for_tenant(self, tenant):
        membership = self.memberships.filter(tenant=tenant, is_active=True).first()
        return membership.role if membership else None


class TenantMembership(AbstractUUID, models.Model):
    """Links a user account to one school with a tenant-scoped role.

    This model belongs to ``user_account`` because it answers an access-control
    question: which account can act inside which school, and as which role.
    School-owned configuration belongs in ``tenants``.
    """
    user = models.ForeignKey(
        UserAccount, on_delete=models.CASCADE, related_name='memberships'
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='memberships'
    )
    role = models.CharField(max_length=ROLE_MAX_LENGTH, choices=RoleChoices.choices)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-joined_at']
        verbose_name = 'Tenant Membership'
        verbose_name_plural = 'Tenant Memberships'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'tenant'],
                name='unique_user_tenant_membership',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f'{self.user} in {self.tenant} as {self.get_role_display()}'
