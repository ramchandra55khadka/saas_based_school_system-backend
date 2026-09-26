"""user_profile app constants."""

# --- UserProfile.gender ---------------------------------------------------------
GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other'),
    ('prefer_not_to_say', 'Prefer not to say'),
]
GENDER_MALE = 'male'
GENDER_FEMALE = 'female'
GENDER_OTHER = 'other'
GENDER_PREFER_NOT_TO_SAY = 'prefer_not_to_say'
GENDER_MAX_LENGTH = 20

# --- UserProfile.nationality -----------------------------------------------------
NATIONALITY_MAX_LENGTH = 100