"""user_account app constants.

Only depends on ``django.db.models``, so importing this module from
``core.constants`` or from any app's ``models.py`` cannot create a cycle.
"""
from django.db.models import TextChoices


class RoleChoices(TextChoices):
    """Role a ``TenantMembership`` grants inside a single school.

    Note there is no ``super_admin`` member: platform-level access is the
    ``UserAccount.is_superuser`` flag (see ``UserAccount.is_super_admin()``),
    because a super admin belongs to no tenant and therefore holds no
    membership.
    """
    ADMIN = 'admin', 'Admin'
    PRINCIPAL = 'principal', 'Principal'
    HOD = 'hod', 'Head of Department'
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'
    PARENT = 'parent', 'Parent/Guardian'
    LIBRARIAN = 'librarian', 'Librarian'
    ACCOUNTANT = 'accountant', 'Accountant'
    STAFF = 'staff', 'Staff'


# --- TenantMembership.role ----------------------------------------------------
ROLE_CHOICES = RoleChoices.choices
ROLE_ADMIN = RoleChoices.ADMIN
ROLE_PRINCIPAL = RoleChoices.PRINCIPAL
ROLE_HOD = RoleChoices.HOD
ROLE_TEACHER = RoleChoices.TEACHER
ROLE_STUDENT = RoleChoices.STUDENT
ROLE_PARENT = RoleChoices.PARENT
ROLE_LIBRARIAN = RoleChoices.LIBRARIAN
ROLE_ACCOUNTANT = RoleChoices.ACCOUNTANT
ROLE_STAFF = RoleChoices.STAFF

# Matches the ``max_length`` on TenantMembership.role — keep the two in sync.
ROLE_MAX_LENGTH = 30

# 'principal' is accepted by several permission checks but is a real
# TenantMembership role, so it is included wherever a "school leadership"
# group is needed.
LEADERSHIP_ROLES = (RoleChoices.ADMIN, RoleChoices.PRINCIPAL)

# --- Role provisioning ----------------------------------------------------------
# Which membership roles each creator role may grant when it provisions a new
# member of a school. Shared by the user-management API and staff onboarding so
# both paths enforce exactly the same escalation rules: an admin may not mint
# another admin, a principal may not mint a peer, and an HOD is limited to
# teachers and students. Platform super admins bypass the matrix -- they may
# grant every role (see ``utils.permissions.grantable_roles``).
CREATABLE_ROLES_BY_CREATOR = {
    RoleChoices.ADMIN: (
        RoleChoices.PRINCIPAL, RoleChoices.HOD, RoleChoices.TEACHER,
        RoleChoices.STUDENT, RoleChoices.PARENT,
        RoleChoices.LIBRARIAN, RoleChoices.ACCOUNTANT, RoleChoices.STAFF,
    ),
    RoleChoices.PRINCIPAL: (
        RoleChoices.HOD, RoleChoices.TEACHER,
        RoleChoices.STUDENT, RoleChoices.PARENT,
        RoleChoices.LIBRARIAN, RoleChoices.ACCOUNTANT, RoleChoices.STAFF,
    ),
    RoleChoices.HOD: (RoleChoices.TEACHER, RoleChoices.STUDENT),
}

