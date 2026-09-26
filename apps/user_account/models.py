import uuid

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.text import slugify
from apps.tenants.models import Tenant

from utils.abstract_model import AbstractUUID
from .managers import UserAccountManager

# Re-exported so ``from user_account.models import RoleChoices`` keeps working;
# the single source of truth lives in constants.py.
from .constants import ROLE_MAX_LENGTH, RoleChoices  # noqa: F401


class UserAccount(AbstractBaseUser, PermissionsMixin):

    # Stable public identifier, distinct from the auto integer PK.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, unique=True)

    username = models.CharField(max_length=300, blank=True, db_index=True)
    email = models.EmailField(db_index=True)
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
    USERNAME_FIELD = 'uuid'
    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['username']
        verbose_name = 'User Account'
        verbose_name_plural = 'User Accounts'


    @classmethod
    def generate_unique_username(cls, email, tenant=None):
        local_part = (email or '').split('@', 1)[0]
        base = slugify(local_part).replace('-', '_') or 'user'
        base = base[:300]
        username = base
        if tenant is None:
            return username

        counter = 2
        qs = cls.objects.filter(memberships__tenant=tenant)
        while qs.filter(username__iexact=username).exists():
            suffix = f'_{counter}'
            username = f'{base[:300 - len(suffix)]}{suffix}'
            counter += 1
        return username

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = type(self).generate_unique_username(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username or self.email or str(self.uuid)

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
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f'{self.user} in {self.tenant} as {self.get_role_display()}'
