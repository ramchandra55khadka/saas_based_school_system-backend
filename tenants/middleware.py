
import uuid
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from accounts.models import TenantMembership
from tenants.models import Tenant


class TenantMiddleware(MiddlewareMixin):
    """
    DRF-ready tenant middleware for shared-schema SaaS.

    Features:
    - Uses DRF's request.user (JWT-compatible)
    - Resolves tenant via JWT claim or TenantMembership
    - Super-admin bypass
    - Public path allowlist
    - Efficient: 1 query max
    """
    PUBLIC_PATHS = {'/api/auth/', '/api/public/', '/admin/'}

    def process_request(self, request):
        # 1. Public paths → skip
        if request.path.startswith(tuple(self.PUBLIC_PATHS)):
            return

        user = request.user
        if not user.is_authenticated:
            raise NotAuthenticated()

        # 2. Super admin → full access
        if user.is_super_admin():
            return

        # 3. Try JWT claim first
        tenant_uuid_str = getattr(request, 'active_tenant_id', None)

        # 4. Fallback: first active membership
        if not tenant_uuid_str:
            membership = (
                TenantMembership.objects
                .filter(user=user, is_active=True)
                .select_related('tenant')
                .first()
            )
            if not membership:
                raise PermissionDenied("No active tenant")
            tenant_uuid_str = str(membership.tenant.tenant_id)

        # 5. Resolve tenant
        try:
            request.tenant = Tenant.objects.get(
                tenant_id=uuid.UUID(tenant_uuid_str)
            )
        except (ValueError, Tenant.DoesNotExist):
            raise PermissionDenied("Invalid tenant")