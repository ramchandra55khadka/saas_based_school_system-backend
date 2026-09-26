"""parents app constants."""
from apps.user_account.constants import RoleChoices

# --- StudentGuardian.relation ------------------------------------------------
GUARDIAN_RELATION_CHOICES = [
    ('father', 'Father'),
    ('mother', 'Mother'),
    ('guardian', 'Guardian'),
    ('other', 'Other'),
]
GUARDIAN_RELATION_FATHER = 'father'
GUARDIAN_RELATION_MOTHER = 'mother'
GUARDIAN_RELATION_GUARDIAN = 'guardian'
GUARDIAN_RELATION_OTHER = 'other'

# Matches the ``max_length`` on StudentGuardian.relation — keep in sync.
GUARDIAN_RELATION_MAX_LENGTH = 30

# Membership role ``Parent.clean()`` requires in the school: a parent profile
# whose account lacks an active ``parent`` membership in the same tenant is
# rejected rather than silently created.
PARENT_REQUIRED_ROLE = RoleChoices.PARENT
