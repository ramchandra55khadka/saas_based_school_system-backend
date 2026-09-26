"""library app constants."""

# --- LibraryMember.member_type -----------------------------------------------
MEMBER_TYPE_CHOICES = [
    ('student', 'Student'),
    ('staff', 'Staff'),
]
MEMBER_TYPE_STUDENT = 'student'
MEMBER_TYPE_STAFF = 'staff'

# --- BookCopy.status ---------------------------------------------------------
BOOK_COPY_STATUS_CHOICES = [
    ('available', 'Available'),
    ('issued', 'Issued'),
    ('lost', 'Lost'),
    ('damaged', 'Damaged'),
]
BOOK_COPY_AVAILABLE = 'available'
BOOK_COPY_ISSUED = 'issued'
BOOK_COPY_LOST = 'lost'
BOOK_COPY_DAMAGED = 'damaged'
BOOK_COPY_DEFAULT_STATUS = BOOK_COPY_AVAILABLE

# --- BookIssue.status --------------------------------------------------------
BOOK_ISSUE_STATUS_CHOICES = [
    ('issued', 'Issued'),
    ('returned', 'Returned'),
    ('lost', 'Lost'),
]
BOOK_ISSUE_ISSUED = 'issued'
BOOK_ISSUE_RETURNED = 'returned'
BOOK_ISSUE_LOST = 'lost'
BOOK_ISSUE_DEFAULT_STATUS = BOOK_ISSUE_ISSUED

# Monetary policy, kept here so the fine/length rules live in one place.
DEFAULT_FINE_AMOUNT = 0

# Matches the ``max_length`` values on the model fields — keep in sync.
MEMBER_TYPE_MAX_LENGTH = 20
BOOK_STATUS_MAX_LENGTH = 20
