"""core app constants shared by mixins and permission classes.

Importing from ``user_account.constants`` is safe: that module only depends on
``django.db.models``, so there is no import cycle.
"""
from apps.user_account.constants import RoleChoices

# Request paths that never require tenant resolution (public endpoints).
PUBLIC_PATHS = {
    '/api/accounts/login/',
    '/api/accounts/logout/',
    '/api/accounts/superadmin/create-tenant/',
    '/api/accounts/token/refresh/',
    '/admin/', '/static/', '/media/',
}

# ---------------------------------------------------------------------------
# Role groups used by the permission classes.
#
# "principal" is a real TenantMembership role (``RoleChoices.PRINCIPAL``), so a
# school head is modelled directly instead of being folded into "admin".
# ---------------------------------------------------------------------------
PRINCIPAL_ROLE = RoleChoices.PRINCIPAL

# IsTenantAdmin / IsAdminOrSuperAdmin
TENANT_ADMIN_ROLES = (RoleChoices.ADMIN, PRINCIPAL_ROLE)
# IsHOD / IsTeacher / IsStudent / IsParent / IsAccountant — single-role checks
# use RoleChoices directly.
# IsAdminOrHOD
ADMIN_PRINCIPAL_HOD_ROLES = (RoleChoices.ADMIN, PRINCIPAL_ROLE, RoleChoices.HOD)
# IsReportsViewer — school analytics (enrolment, attendance, exams, fees).
# The accountant reads the same reports as the school leadership: reports is
# how the fee collection and enrolment figures are presented.
REPORTS_VIEW_ROLES = (
    RoleChoices.ADMIN, PRINCIPAL_ROLE, RoleChoices.HOD, RoleChoices.ACCOUNTANT,
)
# IsAdminOrHODOrTeacher
ADMIN_PRINCIPAL_HOD_TEACHER_ROLES = (
    RoleChoices.ADMIN, PRINCIPAL_ROLE, RoleChoices.HOD, RoleChoices.TEACHER,
)
# IsAdminOrHodUserManagement.has_permission
USER_MANAGEMENT_ROLES = (RoleChoices.ADMIN, PRINCIPAL_ROLE, RoleChoices.HOD)
# IsAdminOrHodUserManagement.has_object_permission
USER_MANAGEMENT_ADMIN_ROLES = (RoleChoices.ADMIN, PRINCIPAL_ROLE)
# IsAdminOrHodUserManagement.has_object_permission (what an HOD may manage)
HOD_MANAGEABLE_ROLES = (RoleChoices.TEACHER, RoleChoices.STUDENT)
# IsFinanceManager — the finance office. Fee types/structures, invoices,
# payments, receipts, refunds, discounts, expenses and payroll are theirs to
# manage, which is why the frontend's "manage_fees" permission includes the
# accountant alongside admin/principal.
FINANCE_MANAGER_ROLES = (RoleChoices.ADMIN, PRINCIPAL_ROLE, RoleChoices.ACCOUNTANT)
