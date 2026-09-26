"""tenants app constants."""
from django.db import models


class DepartmentLevel(models.TextChoices):
    """Department.level choices (moved here from models for reuse)."""

    PRIMARY = 'primary', 'Primary'
    LOWER_SECONDARY = 'lower_secondary', 'Lower Secondary'
    SECONDARY = 'secondary', 'Secondary'
    ADMINISTRATION = 'administration', 'Administration'
    LIBRARY = 'library', 'Library'
    FINANCE = 'finance', 'Finance'
    OTHER = 'other', 'Other'


# --- SchoolSettings ---------------------------------------------------------------
GRADING_SYSTEM_CHOICES = [
    ('percentage', 'Percentage'),
    ('gpa', 'GPA'),
    ('letter', 'Letter Grade'),
]
GRADING_PERCENTAGE = 'percentage'
GRADING_GPA = 'gpa'
GRADING_LETTER = 'letter'
DEFAULT_GRADING_SYSTEM = GRADING_PERCENTAGE

ATTENDANCE_TYPE_CHOICES = [
    ('daily', 'Daily'),
    ('period', 'Per Period'),
]
ATTENDANCE_DAILY = 'daily'
ATTENDANCE_PERIOD = 'period'
DEFAULT_ATTENDANCE_TYPE = ATTENDANCE_DAILY

DEFAULT_ACADEMIC_YEAR_FORMAT = 'YYYY-YYYY'
DEFAULT_TIMEZONE = 'Asia/Kathmandu'
