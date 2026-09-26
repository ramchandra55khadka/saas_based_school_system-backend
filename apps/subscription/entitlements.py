"""Feature-based entitlement checks for tenant subscriptions.

The single source of truth for *what a school may use* is the active
``Subscription -> Plan -> Features`` relationship. Views, permissions and the
frontend ask ``has_feature(tenant, "finance")`` instead of embedding plan-name
checks (``if plan.name == "Premium"``) that rot as new plans are added.

Limits (``max_students``) are a separate concern from features (allowed
modules): a plan both *grants features* and *caps usage*.
"""
from django.utils import timezone
from rest_framework.permissions import BasePermission

from utils.permissions import is_super_admin

from .models import Subscription


def get_active_subscription(tenant):
    """The tenant's currently valid subscription, or ``None``."""
    if tenant is None:
        return None
    now = timezone.now()
    return (
        Subscription.objects.select_related('plan')
        .filter(
            tenant=tenant,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        )
        .first()
    )


def get_active_plan(tenant):
    """The Plan of the tenant's current subscription, or ``None``."""
    subscription = get_active_subscription(tenant)
    return subscription.plan if subscription else None


def has_feature(tenant, feature_key):
    """True when the tenant's active plan grants ``feature_key``.

    Usage: ``has_feature(tenant, FeatureKey.FINANCE)``.
    """
    plan = get_active_plan(tenant)
    if plan is None:
        return False
    return plan.features.filter(key=feature_key, is_active=True).exists()


def get_student_limit(tenant):
    """Max students the tenant's plan allows (a limit, not a feature)."""
    plan = get_active_plan(tenant)
    return plan.max_students if plan else 0


def get_effective_features(tenant):
    """Dict of granted feature keys -> True for the tenant's plan.

    Handy for the frontend to toggle menus: ``{"students": True, ...}``.
    """
    plan = get_active_plan(tenant)
    if plan is None:
        return {}
    keys = plan.features.filter(is_active=True).values_list('key', flat=True)
    return {key: True for key in keys}


class HasFeatureAccess(BasePermission):
    """DRF gate: allow access only when the tenant's plan grants a feature.

    Set ``feature_key`` on the view, or subclass with ``feature_key = ...``::

        class FinanceViewSet(TenantViewSet):
            feature_key = FeatureKey.FINANCE
            permission_classes = [...existing..., HasFeatureAccess]

    Super admins are platform-level and bypass feature gates.
    """
    message = "Your school's plan does not include this feature."

    def has_permission(self, request, view):
        feature_key = getattr(view, 'feature_key', None)
        if feature_key is None:
            return True
        if is_super_admin(request.user):
            return True
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return False
        return has_feature(tenant, feature_key)