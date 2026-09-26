import secrets
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings

from .serializers import (
    EmailTokenObtainPairSerializer, SuperAdminEmailLoginSerializer,
    TenantEmailLoginSerializer, UserSerializer, SignupSerializer,
    UserProfileSerializer, account_full_name,
)
from apps.core.mixins import TenantViewSet, TenantAPIView
from utils.permissions import IsSuperAdmin, IsAdminOrHodUserManagement, grantable_roles
from utils.throttling import LoginRateThrottle, RefreshRateThrottle
from .models import TenantMembership, RoleChoices

User = get_user_model()


def require_trusted_origin(request):
    """Reject cross-origin unsafe requests before issuing or rotating cookies.

    Next rewrites `/api/*` to Django, so Django often sees the backend host
    (`127.0.0.1:8000`) while the browser Origin is the school host
    (`kmc.edunexus.local:3000`). Accept exact CSRF_TRUSTED_ORIGINS and local
    tenant-root subdomains so every school slug does not need custom code.
    """
    origin = request.META.get('HTTP_ORIGIN')
    referer = request.META.get('HTTP_REFERER')
    source = origin or referer
    if not source:
        return

    parsed = urlparse(source)
    source_host = parsed.hostname.lower() if parsed.hostname else ''
    source_port = parsed.port
    source_netloc = parsed.netloc.lower()
    request_host = request.get_host().lower()
    if source_netloc == request_host:
        return

    trusted = {urlparse(item).netloc.lower() for item in settings.CSRF_TRUSTED_ORIGINS}
    if source_netloc in trusted:
        return

    root_domain = getattr(settings, 'TENANT_ROOT_DOMAIN', '').strip().lower().lstrip('.')
    if root_domain and source_host.endswith(f'.{root_domain}'):
        # Local frontend dev server and normal same-scheme tenant pages are OK.
        if parsed.scheme == request.scheme or source_port == 3000:
            return

    raise PermissionDenied('Untrusted authentication origin')


def set_auth_cookies(response, access, refresh=None):
    cookie_kwargs = dict(
        httponly=True,
        samesite=settings.JWT_COOKIE_SAMESITE,
        path='/',
        secure=settings.JWT_COOKIE_SECURE,
    )
    response.set_cookie(
        settings.JWT_ACCESS_COOKIE,
        str(access),
        max_age=settings.JWT_ACCESS_COOKIE_AGE,
        **cookie_kwargs,
    )
    if refresh is not None:
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE,
            str(refresh),
            max_age=settings.JWT_REFRESH_COOKIE_AGE,
            **cookie_kwargs,
        )

    response.set_cookie(
        settings.JWT_CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=settings.JWT_REFRESH_COOKIE_AGE,
        httponly=False,
        samesite=settings.JWT_COOKIE_SAMESITE,
        path='/',
        secure=settings.JWT_COOKIE_SECURE,
    )


def clear_auth_cookies(response):
    cookie_kwargs = dict(samesite=settings.JWT_COOKIE_SAMESITE, path='/')
    response.delete_cookie(settings.JWT_ACCESS_COOKIE, **cookie_kwargs)
    response.delete_cookie(settings.JWT_REFRESH_COOKIE, **cookie_kwargs)
    response.delete_cookie(settings.JWT_CSRF_COOKIE, **cookie_kwargs)
    return response


def validate_refresh_context(refresh, request):
    user_id = refresh.get('user_id')
    active_tenant_id = refresh.get('active_tenant_id')
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        raise InvalidToken('User is inactive or no longer exists')

    host_tenant = getattr(request, 'tenant', None)
    if getattr(request, 'tenant_slug', None) and host_tenant is None:
        raise InvalidToken('School not found')
    if host_tenant is not None and str(host_tenant.tenant_id) != str(active_tenant_id):
        raise InvalidToken('Refresh token does not belong to this school')
    if active_tenant_id and not user.memberships.filter(
        tenant_id=active_tenant_id,
        is_active=True,
    ).exists():
        raise InvalidToken('You no longer have access to this school')

    return user


def attach_tenant_claims(token, membership):
    if membership:
        token['active_tenant_id'] = str(membership.tenant.tenant_id)
        token['active_tenant_slug'] = membership.tenant.slug


class MemberDirectoryView(TenantAPIView):
    """Lightweight directory of the school's active members.

    ``accounts/user-management`` is Admin/HOD-only, which leaves teachers,
    students and parents without a way to pick a message recipient. This
    endpoint exposes only ``id``/``username``/``full_name``/``roles`` to any
    authenticated member of the tenant.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return Response(
                {'message': 'Tenant context missing'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        memberships = (
            TenantMembership.objects
            .filter(tenant=tenant, is_active=True)
            .select_related('user')
            .order_by('user__username')
        )
        users = {}
        for membership in memberships:
            entry = users.setdefault(membership.user_id, {
                'id': membership.user_id,
                'username': membership.user.username,
                'full_name': account_full_name(membership.user),
                'roles': [],
            })
            entry['roles'].append(membership.role)
        return Response(list(users.values()))


class SuperAdminTenantCreateView(generics.CreateAPIView):
    """Super admin creates a new tenant and its initial admin user."""
    serializer_class = SignupSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class UserManagementViewSet(TenantViewSet):
    """Tenant-scoped user management for Admin and HOD roles."""
    # ``TenantQuerysetMixin.get_queryset()`` calls ``super().get_queryset()``,
    # which requires a base queryset to scope to the active tenant.
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHodUserManagement]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_super_admin():
            return qs
        membership = TenantMembership.objects.filter(
            user=self.request.user,
            tenant=self.require_tenant(),
            is_active=True,
        ).first()
        if not membership:
            return qs.none()
        if membership.role in [RoleChoices.ADMIN, RoleChoices.PRINCIPAL]:
            return qs
        if membership.role == RoleChoices.HOD:
            return qs.filter(memberships__role__in=[RoleChoices.TEACHER, RoleChoices.STUDENT])
        return qs.none()

    def perform_create(self, serializer):
        creator = self.request.user
        role = serializer.validated_data.get('role')

        # One shared matrix (``CREATABLE_ROLES_BY_CREATOR``) decides which roles
        # a creator may grant; super admins may grant every role.
        permitted_roles = grantable_roles(creator, self.require_tenant())

        if role not in permitted_roles:
            raise serializers.ValidationError(
                f'You cannot create a user with role "{role}" in this school.'
            )

        user = serializer.save()
        TenantMembership.objects.create(
            user=user,
            tenant=self.require_tenant(),
            role=role,
            is_active=True,
        )

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated, IsSuperAdmin],
        url_path='set-password',
    )
    def set_password(self, request, pk=None):
        """Super admin renews or changes a school user's password.

        Intended for resetting a school admin's credentials — call with
        ``?tenant_id=<uuid>`` so the object lookup is tenant-scoped:
        ``POST /accounts/user-management/<id>/set-password/?tenant_id=...``
        with ``{"password": "..."}``.
        """
        user = self.get_object()
        new_password = (request.data.get('password') or '').strip()
        if len(new_password) < 8:
            return Response(
                {'message': 'Password must be at least 8 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save(update_fields=['password'])
        return Response({
            'status': 'success',
            'message': f'Password updated for "{user.username}".',
        })


class BaseCookieLoginView(TokenObtainPairView):
    """Shared cookie/claim plumbing for the two login contexts.

    The two entry points differ only in *which* tenant context they require, so
    everything else — origin check, throttling, cookie names, claim attachment
    — lives here and :meth:`resolve_membership` is the single override point.
    """

    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    #: Returned in the JSON body so the client can tell the contexts apart.
    success_message = 'Login successful'

    def assert_context(self, request):
        """Reject a request that arrived in the wrong login context.

        Runs *before* credential validation so that "you used the wrong page"
        is reported as a 400 about context, rather than as a 401 that looks like
        a wrong password.
        """

    def resolve_membership(self, user, request):
        """Return the TenantMembership to scope the token to, or None.

        Must be implemented by each concrete login view: it is the whole reason
        the two logins are separate endpoints.
        """
        raise NotImplementedError

    def post(self, request, *args, **kwargs):
        require_trusted_origin(request)
        self.assert_context(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        # Raises before any token is minted, so a rejected context never
        # produces a partially-valid session.
        membership = self.resolve_membership(user, request)

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        attach_tenant_claims(access, membership)
        attach_tenant_claims(refresh, membership)

        resp = Response({
            'message': self.success_message,
            'login_context': self.login_context,
        })
        set_auth_cookies(resp, access, refresh)
        return resp

    #: Human-readable marker echoed to the client.
    login_context = 'unknown'


class TenantLoginView(BaseCookieLoginView):
    """``POST /api/auth/login/`` — sign in to one school.

    Requires a school subdomain: the tenant is resolved from the request host by
    ``TenantMiddleware``, and the account must hold an active membership in that
    exact school. There is deliberately no "pick a tenant for me" fallback — a
    token minted without a school context could not scope any query, and
    defaulting to the caller's first membership would hand out a session for an
    arbitrary school.
    """

    login_context = 'tenant'
    success_message = 'Login successful'
    serializer_class = TenantEmailLoginSerializer

    def assert_context(self, request):
        host_slug = getattr(request, 'tenant_slug', None)
        if host_slug and getattr(request, 'tenant', None) is None:
            raise ValidationError({'message': 'School not found.'})
        if getattr(request, 'tenant', None) is None:
            raise ValidationError({
                'message': 'Open your school\'s login page to sign in.'
            })

    def resolve_membership(self, user, request):
        membership = TenantMembership.objects.filter(
            user=user, tenant=request.tenant, is_active=True
        ).select_related('tenant').first()
        if membership is None:
            raise ValidationError({
                'message': 'You do not have access to this school.'
            })
        return membership


class SuperAdminLoginView(BaseCookieLoginView):
    """``POST /api/auth/super-user/login/`` — platform super admin sign-in.

    The mirror image of :class:`TenantLoginView`: it is only reachable from a
    platform host (a school subdomain is rejected) and only for
    ``is_superuser`` accounts. The issued token deliberately carries **no**
    tenant claim, so platform endpoints stay tenant-agnostic.
    """

    login_context = 'super_admin'
    success_message = 'Super admin login successful'
    serializer_class = SuperAdminEmailLoginSerializer

    def assert_context(self, request):
        if getattr(request, 'tenant', None) is not None:
            raise ValidationError({
                'message': 'Super admin sign-in is only available on the platform page.'
            })

    def resolve_membership(self, user, request):
        if not user.is_super_admin():
            raise PermissionDenied('Super admin access only.')
        return None


class CookieTokenRefreshView(APIView):
    """Refresh the JWT using the HttpOnly refresh cookie.

    With ``SIMPLE_JWT['ROTATE_REFRESH_TOKENS']`` enabled every refresh also
    mints a NEW refresh cookie and blacklists the presented one, so a stolen
    refresh token becomes useless as soon as the legitimate client refreshes
    (``BLACKLIST_AFTER_ROTATION``).
    """
    permission_classes = []
    # Do NOT run DRF/JWT authentication here. The middleware copies the access
    # cookie into the Authorization header, and once that access token is
    # expired (the exact moment a refresh is needed) JWTAuthentication raises
    # before this view runs, returning 401 even though the refresh cookie is
    # valid.
    authentication_classes = []
    throttle_classes = [RefreshRateThrottle]

    def post(self, request, *args, **kwargs):
        require_trusted_origin(request)
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not refresh_token:
            return Response(
                {'message': 'Refresh token not found'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(refresh_token)
            validate_refresh_context(refresh, request)
            active_tenant_id = refresh.get('active_tenant_id')
            active_tenant_slug = refresh.get('active_tenant_slug')

            # Rotate the same way SimpleJWT's TokenRefreshSerializer does:
            # blacklist the presented token, then give it a fresh jti/exp/iat.
            if jwt_api_settings.ROTATE_REFRESH_TOKENS:
                if jwt_api_settings.BLACKLIST_AFTER_ROTATION:
                    try:
                        refresh.blacklist()
                    except AttributeError:  # blacklist app not installed
                        pass
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()
                if active_tenant_id:
                    refresh['active_tenant_id'] = active_tenant_id
                if active_tenant_slug:
                    refresh['active_tenant_slug'] = active_tenant_slug
            access = refresh.access_token  # inherits the tenant claim

            resp = Response({
                'message': 'Token refreshed successfully',
            })
            set_auth_cookies(resp, access, refresh)
            return resp
        except (InvalidToken, TokenError):
            return Response(
                {'message': 'Invalid refresh token'},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class LogoutView(APIView):
    """Clear the JWT cookies and revoke the refresh token.

    Intentionally unauthenticated: a caller with an expired access token must
    still be able to log out (the cookies are cleared either way, and the
    refresh token is blacklisted when it is still valid).
    """
    permission_classes = []
    # Same as CookieTokenRefreshView: an expired access cookie copied to the
    # Authorization header would otherwise make JWTAuthentication 401 before
    # the view runs.
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        require_trusted_origin(request)
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if refresh_token:
            try:
                # Revokes the refresh token; an already-invalid/blacklisted
                # token raises and is ignored.
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass

        response = Response({'message': 'Logout successful'}, status=200)
        return clear_auth_cookies(response)


class MeView(APIView):
    """Returns the current authenticated user's profile and memberships."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response({
            'status': 'success',
            'data': serializer.data,
        })
