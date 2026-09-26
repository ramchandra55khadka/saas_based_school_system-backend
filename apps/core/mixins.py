# core/mixins.py
import uuid
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.core.constants import PUBLIC_PATHS
from utils.permissions import is_super_admin
from apps.tenants.models import Tenant

def validate_instance(instance):
    """Run the model's ``full_clean()`` and re-raise it as a DRF ``ValidationError``.

    Shared by ``TenantViewSet`` (after every write) and by serializers that build
    several rows themselves (e.g. staff onboarding), so model-level rules such as
    ``Staff.clean()`` and the unique-constraint checks turn into a clean 400
    *inside* the caller's transaction instead of an unhandled 500.
    """
    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)


class TenantRequiredMixin:
    """
    Resolves ``request.tenant`` from the ``active_tenant_id`` claim in the JWT.

    Authentication and tenant resolution are deliberately hooked into
    ``perform_authentication()`` and **not** ``dispatch()``. DRF's
    ``APIView.dispatch()`` is what calls ``initialize_request()`` (wrapping the raw
    Django ``HttpRequest`` in a DRF ``Request``) and then
    ``initial() -> perform_authentication()``, which finally populates
    ``request.user`` and ``request.auth``.

    A mixin that defines ``dispatch()`` therefore runs *before* any authentication
    has happened: it sees the raw Django request, whose ``user`` is an
    ``AnonymousUser`` because there is no session (auth is JWT-in-cookie). That made
    every tenant-scoped endpoint answer ``401 {"detail": "Authentication required"}``
    even with a perfectly valid token.

    ``perform_authentication()`` runs after the JWT is validated but *before*
    ``check_permissions()``, so ``request.tenant`` is available to permission
    classes that scope their checks to a tenant.
    """

    def perform_authentication(self, request):
        super().perform_authentication(request)
        self.resolve_tenant(request)

    def resolve_tenant(self, request):
        """Attach ``request.tenant`` when the request is bound to a school."""
        path = request.path_info.rstrip('/')
        if any(path.startswith(p.rstrip('/')) for p in PUBLIC_PATHS):
            return

        if not request.user.is_authenticated:
            raise NotAuthenticated("Authentication required")

        # Super admins are platform-level and not bound to a single school, but
        # they may act on a specific school by passing ?tenant_id=<uuid>.
        if is_super_admin(request.user):
            tenant = self._tenant_from_query_param(request)
            if tenant is not None:
                request.tenant = tenant
            return

        # request.auth is the validated token set by JWTAuthentication.
        token = getattr(request, "auth", None)
        if token is None:
            raise AuthenticationFailed("Invalid token")

        payload = getattr(token, "payload", None)
        if not isinstance(payload, dict):
            raise AuthenticationFailed("Invalid token payload")

        tenant_id = payload.get("active_tenant_id")
        if not tenant_id:
            raise ValidationError({"message": "Tenant context missing"})

        tenant = self._lookup_tenant(tenant_id)

        # Re-validate the membership on every request: the JWT's
        # ``active_tenant_id`` claim is minted at login, so a membership that is
        # deactivated (or deleted) after that point must not keep working until
        # the token expires. This is what makes de-provisioning immediate.
        if not request.user.memberships.filter(tenant=tenant, is_active=True).exists():
            raise AuthenticationFailed("You no longer have access to this school")

        request.tenant = tenant

    @staticmethod
    def _lookup_tenant(tenant_id):
        try:
            return Tenant.objects.get(tenant_id=uuid.UUID(str(tenant_id)))
        except (TypeError, ValueError, AttributeError, Tenant.DoesNotExist):
            raise ValidationError({"message": "Invalid tenant ID"})

    @staticmethod
    def _tenant_from_query_param(request):
        """Resolve an explicit ``?tenant_id=`` (super admins only)."""
        raw = request.query_params.get("tenant_id")
        if not raw:
            return None
        return TenantRequiredMixin._lookup_tenant(raw)

    def require_tenant(self):
        """Return ``request.tenant`` or raise a clear 400 when there is none."""
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise ValidationError({
                "message": (
                    "No active tenant for this request. "
                    "Super admins must pass ?tenant_id=<uuid>."
                )
            })
        return tenant

    # Backwards-compatible no-op shim kept for any code that still expects
    # ``dispatch`` to be overridden here. Tenant resolution happens in
    # ``perform_authentication`` instead - see the class docstring.
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

class TenantQuerysetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        
        if not tenant:
            return qs.none()
            
        if qs.model.__name__ == 'UserAccount':
            # TenantMembership.user uses related_name='memberships', so the
            # reverse lookup is ``memberships__tenant`` (the default
            # lowercased ``tenantmembership__tenant`` does not exist and
            # raises FieldError).
            return qs.filter(memberships__tenant=tenant)
        elif hasattr(qs.model, 'tenant'):
            return qs.filter(tenant=tenant)
            
        return qs.none()


class TenantAPIView(TenantRequiredMixin, APIView):
    """``APIView`` variant that resolves ``request.tenant``.

    Report views and other plain ``APIView``s need the same cookie -> JWT ->
    tenant-context chain as ``TenantViewSet`` without DRF-ViewSet plumbing.
    ``TenantRequiredMixin.perform_authentication`` runs via ``APIView.initial()``,
    so ``request.tenant`` is set before permission checks (Bug E fix).
    """
    permission_classes = [IsAuthenticated]


class TenantViewSet(TenantRequiredMixin, TenantQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            tenant = getattr(self.request, "tenant", None)
            if tenant and hasattr(serializer.Meta.model, 'tenant'):
                instance = serializer.save(tenant=tenant)
            else:
                instance = serializer.save()
            self._validate_instance(instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._validate_instance(instance)

    @staticmethod
    def _validate_instance(instance):
        validate_instance(instance)
