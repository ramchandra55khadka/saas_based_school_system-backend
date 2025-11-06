"""
Helper utilities for tenant-based filtering and membership access.
"""

from accounts.models import TenantMembership

def get_current_tenant(request):
    """Returns the tenant (organization) from the request."""
    return getattr(request, "tenant", None)


def get_current_membership(user):
    """
    Returns the active tenant membership of a user.
    Useful for checking role within tenant context.
    """
    if not user.is_authenticated:
        return None
    return TenantMembership.objects.filter(user=user, is_active=True).first()


def is_user_in_tenant(user, tenant):
    """Checks if user belongs to a specific tenant."""
    return TenantMembership.objects.filter(user=user, tenant=tenant, is_active=True).exists()
