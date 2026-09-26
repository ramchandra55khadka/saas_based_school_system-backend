from rest_framework import viewsets, permissions
from rest_framework.response import Response
from apps.core.mixins import TenantViewSet
from utils.permissions import IsAdminOrHOD, IsTenantAdmin, IsSuperAdmin
from .models import Department, Tenant, SchoolSettings
from .serializers import (
    TenantSerializer, TenantDetailSerializer,
    SchoolSettingsSerializer, DepartmentSerializer,
)


class SchoolProfileViewSet(viewsets.ModelViewSet):
    """School profile management. Admin can view/update their own school.

    Deletion is platform-level and destructive (the tenant and every
    tenant-scoped record cascade), so it is reserved for the super admin.
    """
    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        # Only the super admin may delete a school; tenant admins keep
        # view/update rights on their own school.
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'is_super_admin') and user.is_super_admin():
            return Tenant.objects.all()
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            # This viewset does not run TenantRequiredMixin, so fall back to
            # the caller's own membership — otherwise a tenant admin (who the
            # permission class allows) would always see an empty queryset.
            membership = user.memberships.filter(
                is_active=True
            ).select_related('tenant').first()
            tenant = membership.tenant if membership else None
        if tenant:
            return Tenant.objects.filter(tenant_id=tenant.tenant_id)
        return Tenant.objects.none()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TenantDetailSerializer
        return TenantSerializer


class SchoolSettingsViewSet(viewsets.ModelViewSet):
    """School settings management. Admin can view/update settings."""
    serializer_class = SchoolSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return SchoolSettings.objects.filter(tenant=tenant)
        return SchoolSettings.objects.none()


class DepartmentViewSet(TenantViewSet):
    """Departments of the active school (the Academics → Departments tab).

    Reads are open to every member (the staff form and the teacher onboarding
    dialog list departments as a pick-list); managing them follows the rest of
    the admin API — admin, principal and HOD (``IsAdminOrHOD``).
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # A super admin writing without ?tenant_id= has no active school; make
        # that a clear 400 ("pass ?tenant_id=<uuid>") instead of a 500 from the
        # non-nullable `tenant` FK.
        self.require_tenant()
        super().perform_create(serializer)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminOrHOD()]
        return super().get_permissions()
