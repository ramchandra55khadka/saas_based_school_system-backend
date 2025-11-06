
"""
Mixins to automatically filter data per-tenant and simplify tenant-safe views.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

class TenantQuerysetMixin:
    """
    Automatically filters objects by the tenant from the request.
    Prevents cross-tenant data leakage.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return qs.filter(tenant=tenant)
        return qs.none()  # if no tenant (e.g. super admin-only views)


class TenantViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    """
    A base class for all tenant-bound ViewSets.
    Automatically sets tenant on creation.
    """
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
