"""teachers app constants."""
from apps.user_account.constants import RoleChoices

# Roles that count as "teaching staff" for Teacher membership validation.
TEACHING_MEMBERSHIP_ROLES = (
    RoleChoices.TEACHER,
    RoleChoices.HOD,
    RoleChoices.PRINCIPAL,
)

# The ``Teacher`` columns the "Add teacher" onboarding payload fills: ``uuid``
# and the timestamps are bookkeeping and the record hangs off ``staff.Staff``,
# so every other column must appear here -- a test asserts the tuple stays
# equal to the model's fields, which is what stops a column from being
# forgotten (same idea as ``PROFILE_ONBOARD_FIELDS``).
TEACHER_ONBOARD_FIELDS = (
    'teaching_license_number', 'primary_subject', 'class_teacher_section',
    'max_weekly_periods', 'office_hours', 'bio',
)

# --- TeacherAttendance.status ------------------------------------------------
TEACHER_ATTENDANCE_STATUS_CHOICES = [
    ('present', 'Present'),
    ('absent', 'Absent'),
    ('late', 'Late'),
    ('on_leave', 'On Leave'),
]
ATTENDANCE_PRESENT = 'present'
ATTENDANCE_ABSENT = 'absent'
ATTENDANCE_LATE = 'late'
ATTENDANCE_ON_LEAVE = 'on_leave'

# --- LeaveRequest.leave_type --------------------------------------------------
LEAVE_TYPE_CHOICES = [
    ('sick', 'Sick Leave'),
    ('casual', 'Casual Leave'),
    ('earned', 'Earned Leave'),
    ('maternity', 'Maternity Leave'),
    ('other', 'Other'),
]
LEAVE_SICK = 'sick'
LEAVE_CASUAL = 'casual'
LEAVE_EARNED = 'earned'
LEAVE_MATERNITY = 'maternity'
LEAVE_OTHER = 'other'

# --- LeaveRequest.status ------------------------------------------------------
LEAVE_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]
LEAVE_PENDING = 'pending'
LEAVE_APPROVED = 'approved'
LEAVE_REJECTED = 'rejected'
LEAVE_DEFAULT_STATUS = LEAVE_PENDING
