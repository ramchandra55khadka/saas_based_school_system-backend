"""subscription app constants."""

from django.db import models

# Plan field defaults (used by the Plan model only; plan pricing/duration/
# student caps live in the database and are maintained by super admins).
DEFAULT_PLAN_DURATION_DAYS = 30
DEFAULT_PLAN_MAX_STUDENTS = 100


class SubscriptionRequestType(models.TextChoices):
    """What a school is asking for when it opens a subscription request."""
    RENEW = "renew", "Renew"
    CHANGE_PLAN = "change_plan", "Change Plan"


class SubscriptionRequestStatus(models.TextChoices):
    """Lifecycle of a school's subscription request."""
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class FeatureKey(models.TextChoices):
    """Every functional area a plan can entitle a school to use.

    These keys are stable identifiers. Backend code asks
    ``has_feature(tenant, FeatureKey.FINANCE)``; it never compares plan names.
    """
    STUDENTS = "students", "Students"
    TEACHERS = "teachers", "Teachers"
    STAFF = "staff", "Staff"
    PARENTS = "parents", "Parents"
    ACADEMICS = "academics", "Academics"
    COMMUNICATION = "communication", "Communication"
    FINANCE = "finance", "Finance"
    LIBRARY = "library", "Library"
    REPORTS = "reports", "Reports"