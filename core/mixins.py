# core/mixins.py
import uuid
from django.http import JsonResponse
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from tenants.models import Tenant


PUBLIC_PATHS = {
    '/api/accounts/login/',
    '/api/accounts/logout/',
    '/api/accounts/superadmin/create-tenant/',
    '/api/accounts/token/refresh/',
    '/admin/', '/static/', '/media/',
}


# core/mixins.py
class TenantRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        path = request.path_info.rstrip('/')

        if any(path.startswith(p.rstrip('/')) for p in PUBLIC_PATHS):
            return super().dispatch(request, *args, **kwargs)

        if not request.user.is_authenticated:
            return JsonResponse({"detail": "Authentication required"}, status=401)

        if getattr(request.user, "is_super_admin", False):
            return super().dispatch(request, *args, **kwargs)

        # CRITICAL: request.auth is set by JWTAuthentication (token object)
        if not hasattr(request, "auth") or not request.auth:
            return JsonResponse({"message": "Invalid token"}, status=401)

        payload = request.auth.payload
        if not isinstance(payload, dict):
            return JsonResponse({"message": "Invalid token payload"}, status=401)

        tenant_id = payload.get("active_tenant_id")
        if not tenant_id:
            return JsonResponse({"message": "Tenant context missing"}, status=400)

        try:
            request.tenant = Tenant.objects.get(tenant_id=uuid.UUID(tenant_id))
        except (ValueError, Tenant.DoesNotExist):
            return JsonResponse({"message": "Invalid tenant ID"}, status=400)

        return super().dispatch(request, *args, **kwargs)

class TenantQuerysetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return qs.filter(tenantmembership__tenant=tenant)
        return qs.none()


class TenantViewSet(TenantRequiredMixin, TenantQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]