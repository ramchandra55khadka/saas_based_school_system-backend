"""communication app constants."""

# --- Announcement.target_audience -------------------------------------------------
TARGET_AUDIENCE_CHOICES = [
    ('all', 'All Users'),
    ('teachers', 'All Teachers'),
    ('students', 'All Students'),
    ('parents', 'All Parents'),
]
TARGET_ALL = 'all'
TARGET_TEACHERS = 'teachers'
TARGET_STUDENTS = 'students'
TARGET_PARENTS = 'parents'
DEFAULT_TARGET_AUDIENCE = TARGET_ALL

# Visibility rules used by AnnouncementViewSet.get_queryset():
# everyone sees broadcasts addressed to "all" plus their own audience.
TEACHER_VISIBLE_AUDIENCES = (TARGET_ALL, TARGET_TEACHERS)
STUDENT_VISIBLE_AUDIENCES = (TARGET_ALL, TARGET_STUDENTS)
PARENT_VISIBLE_AUDIENCES = (TARGET_ALL, TARGET_PARENTS)
