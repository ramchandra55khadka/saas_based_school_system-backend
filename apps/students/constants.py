"""students app constants."""
from apps.user_account.constants import RoleChoices

# --- Student.blood_group --------------------------------------------------------
# Matches the ``max_length`` on Student.blood_group — keep in sync.
BLOOD_GROUP_MAX_LENGTH = 10

# Membership role ``Student.clean()`` requires in the school: a student record
# whose account lacks an active ``student`` membership in the same tenant is
# rejected rather than silently created.
STUDENT_REQUIRED_ROLE = RoleChoices.STUDENT

# --- StudentDocument.document_type ---------------------------------------------
DOCUMENT_TYPE_CHOICES = [
    ('birth_certificate', 'Birth Certificate'),
    ('transfer_certificate', 'Transfer Certificate'),
    ('marksheet', 'Marksheet'),
    ('photo', 'Photo'),
    ('other', 'Other'),
]
DOCUMENT_BIRTH_CERTIFICATE = 'birth_certificate'
DOCUMENT_TRANSFER_CERTIFICATE = 'transfer_certificate'
DOCUMENT_MARKSHEET = 'marksheet'
DOCUMENT_PHOTO = 'photo'
DOCUMENT_OTHER = 'other'

# --- StudentAttendance.status ---------------------------------------------------
# NOTE: unlike TeacherAttendance there is no 'on_leave' here; the shared
# frontend AttendanceStatus type still carries it for teacher records.
STUDENT_ATTENDANCE_STATUS_CHOICES = [
    ('present', 'Present'),
    ('absent', 'Absent'),
    ('late', 'Late'),
    ('excused', 'Excused'),
]
ATTENDANCE_PRESENT = 'present'
ATTENDANCE_ABSENT = 'absent'
ATTENDANCE_LATE = 'late'
ATTENDANCE_EXCUSED = 'excused'

# --- Exam.exam_type -------------------------------------------------------------
EXAM_TYPE_CHOICES = [
    ('unit_test', 'Unit Test'),
    ('midterm', 'Midterm'),
    ('final', 'Final'),
    ('other', 'Other'),
]
EXAM_UNIT_TEST = 'unit_test'
EXAM_MIDTERM = 'midterm'
EXAM_FINAL = 'final'
EXAM_OTHER = 'other'
