"""Reusable DRF permissions for tenant-aware school roles."""
from rest_framework.permissions import BasePermission

from apps.core.constants import (
    ADMIN_PRINCIPAL_HOD_ROLES,
    ADMIN_PRINCIPAL_HOD_TEACHER_ROLES,
    FINANCE_MANAGER_ROLES,
    HOD_MANAGEABLE_ROLES,
    REPORTS_VIEW_ROLES,
    RoleChoices,
    TENANT_ADMIN_ROLES,
    USER_MANAGEMENT_ADMIN_ROLES,
    USER_MANAGEMENT_ROLES,
)
from apps.user_account.constants import CREATABLE_ROLES_BY_CREATOR
from apps.user_account.models import TenantMembership


def is_super_admin(user):
    """Platform-level super admin, independent from school memberships."""
    return bool(user and user.is_authenticated and user.is_superuser)


def get_active_membership(user, tenant=None):
    if not user or not user.is_authenticated:
        return None
    qs = TenantMembership.objects.filter(user=user, is_active=True)
    if tenant is not None:
        qs = qs.filter(tenant=tenant)
    return qs.first()


def get_membership_role(user, tenant=None):
    membership = get_active_membership(user, tenant)
    return membership.role if membership else None


def grantable_roles(user, tenant=None):
    """Membership roles ``user`` is allowed to grant to a new member of ``tenant``.

    Super admins may grant every role; a school member is limited by
    ``CREATABLE_ROLES_BY_CREATOR`` (the matrix both the user-management API and
    staff onboarding enforce).
    """
    if is_super_admin(user):
        return tuple(choice for choice, _label in RoleChoices.choices)
    return tuple(CREATABLE_ROLES_BY_CREATOR.get(get_membership_role(user, tenant), ()))


def has_tenant_role(user, roles, tenant=None, allow_super_admin=False):
    if allow_super_admin and is_super_admin(user):
        return True
    if not user or not user.is_authenticated:
        return False
    qs = TenantMembership.objects.filter(user=user, is_active=True, role__in=roles)
    if tenant is not None:
        qs = qs.filter(tenant=tenant)
    return qs.exists()


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_super_admin(request.user)


class HasTenantRole(BasePermission):
    roles = ()
    allow_super_admin = False

    def has_permission(self, request, view):
        return has_tenant_role(
            request.user,
            self.roles,
            getattr(request, 'tenant', None),
            allow_super_admin=self.allow_super_admin,
        )


class IsTenantAdmin(HasTenantRole):
    roles = TENANT_ADMIN_ROLES
    allow_super_admin = True


class IsAdmin(HasTenantRole):
    roles = (RoleChoices.ADMIN,)


class IsPrincipal(HasTenantRole):
    roles = (RoleChoices.PRINCIPAL,)


class IsHOD(HasTenantRole):
    roles = (RoleChoices.HOD,)


class IsTeacher(HasTenantRole):
    roles = (RoleChoices.TEACHER,)


class IsStudent(HasTenantRole):
    roles = (RoleChoices.STUDENT,)


class IsParent(HasTenantRole):
    roles = (RoleChoices.PARENT,)


class IsLibrarian(HasTenantRole):
    roles = (RoleChoices.LIBRARIAN,)


class IsAccountant(HasTenantRole):
    roles = (RoleChoices.ACCOUNTANT,)


class IsStaff(HasTenantRole):
    roles = (RoleChoices.STAFF,)


class IsAdminOrHOD(HasTenantRole):
    roles = ADMIN_PRINCIPAL_HOD_ROLES
    allow_super_admin = True


class IsFinanceManager(HasTenantRole):
    """Who may write finance records: the finance office.

    Admin, principal and accountant — the roles the frontend's ``manage_fees``
    permission shows the Fees page to. Everyone else in the school keeps read
    access (role-scoped by the viewset).
    """
    roles = FINANCE_MANAGER_ROLES
    allow_super_admin = True


class IsAdminOrHODOrTeacher(HasTenantRole):
    roles = ADMIN_PRINCIPAL_HOD_TEACHER_ROLES
    allow_super_admin = True


class IsReportsViewer(HasTenantRole):
    """School analytics viewers: admin, principal, HOD and the accountant."""
    roles = REPORTS_VIEW_ROLES
    allow_super_admin = True


class IsAdminOrSuperAdmin(HasTenantRole):
    roles = TENANT_ADMIN_ROLES
    allow_super_admin = True


class IsStaffOrAdmin(HasTenantRole):
    roles = (
        RoleChoices.ADMIN,
        RoleChoices.PRINCIPAL,
        RoleChoices.HOD,
        RoleChoices.TEACHER,
        RoleChoices.LIBRARIAN,
        RoleChoices.ACCOUNTANT,
        RoleChoices.STAFF,
    )
    allow_super_admin = True


class IsAdminOrHodUserManagement(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return False
        if is_super_admin(request.user):
            return True
        membership = get_active_membership(request.user, tenant)
        return bool(membership and membership.role in USER_MANAGEMENT_ROLES)

    def has_object_permission(self, request, view, obj):
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return False

        obj_tenant_ids = [m.tenant_id for m in obj.memberships.all() if m.is_active]

        if is_super_admin(request.user):
            return tenant.tenant_id in obj_tenant_ids

        requester_role = get_membership_role(request.user, tenant)
        if requester_role in USER_MANAGEMENT_ADMIN_ROLES:
            return tenant.tenant_id in obj_tenant_ids
        if requester_role == RoleChoices.HOD:
            return (
                tenant.tenant_id in obj_tenant_ids
                and obj.memberships.filter(
                    tenant=tenant,
                    is_active=True,
                    role__in=HOD_MANAGEABLE_ROLES,
                ).exists()
            )
        return False
