"""staff app constants."""
from apps.user_account.constants import RoleChoices

DESIGNATION_CHOICES = [
    ('principal', 'Principal'),
    ('teacher', 'Teacher'),
    ('hod', 'Head of Department'),
    ('librarian', 'Librarian'),
    ('accountant', 'Accountant'),
    ('admin', 'Admin Staff'),
    ('support', 'Support Staff'),
    ('other', 'Other'),
]
DESIGNATION_PRINCIPAL = 'principal'
DESIGNATION_TEACHER = 'teacher'
DESIGNATION_HOD = 'hod'
DESIGNATION_LIBRARIAN = 'librarian'
DESIGNATION_ACCOUNTANT = 'accountant'
DESIGNATION_ADMIN = 'admin'
DESIGNATION_SUPPORT = 'support'
DESIGNATION_OTHER = 'other'
DESIGNATION_DEFAULT = DESIGNATION_OTHER

# Membership roles that make a user account eligible for each designation.
# ``Staff.clean()`` rejects a profile whose account holds no matching
# role in the school.
DESIGNATION_ALLOWED_ROLES = {
    DESIGNATION_PRINCIPAL: [RoleChoices.PRINCIPAL, RoleChoices.ADMIN],
    DESIGNATION_TEACHER: [RoleChoices.TEACHER, RoleChoices.HOD, RoleChoices.PRINCIPAL],
    DESIGNATION_HOD: [RoleChoices.HOD, RoleChoices.TEACHER],
    DESIGNATION_LIBRARIAN: [RoleChoices.LIBRARIAN],
    DESIGNATION_ACCOUNTANT: [RoleChoices.ACCOUNTANT],
    DESIGNATION_ADMIN: [RoleChoices.ADMIN, RoleChoices.PRINCIPAL],
    DESIGNATION_SUPPORT: [RoleChoices.STAFF],
    DESIGNATION_OTHER: [RoleChoices.STAFF, RoleChoices.ADMIN, RoleChoices.PRINCIPAL],
}

DESIGNATION_MAX_LENGTH = 30
EMPLOYEE_ID_MAX_LENGTH = 50

# Membership role granted to the user account staff onboarding creates for a
# designation. ``Staff.clean()`` requires the account role to be one of
# ``DESIGNATION_ALLOWED_ROLES[designation]``; the first entry of each list is the
# natural (least privileged) choice -- a teacher gets 'teacher', not 'principal'.
DESIGNATION_DEFAULT_ROLE = {
    designation: allowed_roles[0]
    for designation, allowed_roles in DESIGNATION_ALLOWED_ROLES.items()
}

QUALIFICATION_PLUS_TWO = 'plus_two'
QUALIFICATION_DIPLOMA = 'diploma'
QUALIFICATION_BACHELOR = 'bachelor'
QUALIFICATION_MASTER = 'master'
QUALIFICATION_MPHIL = 'mphil'
QUALIFICATION_PHD = 'phd'
QUALIFICATION_OTHER = 'other'
QUALIFICATION_CHOICES = [
    (QUALIFICATION_PLUS_TWO, '+2'),
    (QUALIFICATION_DIPLOMA, 'Diploma'),
    (QUALIFICATION_BACHELOR, 'Bachelor'),
    (QUALIFICATION_MASTER, 'Master'),
    (QUALIFICATION_MPHIL, 'MPhil'),
    (QUALIFICATION_PHD, 'PhD'),
    (QUALIFICATION_OTHER, 'Other'),
]
QUALIFICATION_MAX_LENGTH = 30

# Backwards-compatible aliases for imports that have not migrated yet.
STAFF_TYPE_CHOICES = DESIGNATION_CHOICES
STAFF_TYPE_TEACHER = DESIGNATION_TEACHER
