from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings

from .serializers import (
    EmailTokenObtainPairSerializer, UserSerializer, SignupSerializer,
    UserProfileSerializer, account_full_name,
)
from apps.core.mixins import TenantViewSet, TenantAPIView
from utils.permissions import IsSuperAdmin, IsAdminOrHodUserManagement, grantable_roles
from .models import TenantMembership, RoleChoices

User = get_user_model()


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


class CookieTokenObtainPairView(TokenObtainPairView):
    """Email+password JWT login that sets HttpOnly cookies and embeds tenant claim."""

    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        membership = TenantMembership.objects.filter(
            user=user, is_active=True
        ).select_related('tenant').first()
        if membership:
            tenant_id = str(membership.tenant.tenant_id)
            access['active_tenant_id'] = tenant_id
            refresh['active_tenant_id'] = tenant_id

        resp = Response({
            'message': 'Login successful',
        })
        cookie_kwargs = dict(
            httponly=True, samesite='Lax', path='/',
            secure=not settings.DEBUG,  # HTTPS-only outside development
        )
        resp.set_cookie(settings.JWT_ACCESS_COOKIE, str(access), **cookie_kwargs)
        resp.set_cookie(settings.JWT_REFRESH_COOKIE, str(refresh), **cookie_kwargs)
        # Returning the raw tokens in the body defeats the HttpOnly cookies (an
        # XSS can read them). Keep them available to a local dev frontend only.
        if settings.DEBUG:
            resp.data['access_token'] = str(access)
            resp.data['refresh_token'] = str(refresh)
        return resp


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

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not refresh_token:
            return Response(
                {'message': 'Refresh token not found'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(refresh_token)
            active_tenant_id = refresh.get('active_tenant_id')

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
            access = refresh.access_token  # inherits the tenant claim

            resp = Response({
                'message': 'Token refreshed successfully',
            })
            cookie_kwargs = dict(
                httponly=True, samesite='Lax', path='/',
                secure=not settings.DEBUG,
            )
            resp.set_cookie(settings.JWT_ACCESS_COOKIE, str(access), **cookie_kwargs)
            resp.set_cookie(settings.JWT_REFRESH_COOKIE, str(refresh), **cookie_kwargs)
            if settings.DEBUG:
                resp.data['access_token'] = str(access)
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
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if refresh_token:
            try:
                # Revokes the refresh token; an already-invalid/blacklisted
                # token raises and is ignored.
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass

        cookie_kwargs = dict(samesite='Lax', path='/')
        response = Response({'message': 'Logout successful'}, status=200)
        response.delete_cookie(settings.JWT_ACCESS_COOKIE, **cookie_kwargs)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE, **cookie_kwargs)
        return response


class MeView(APIView):
    """Returns the current authenticated user's profile and memberships."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response({
            'status': 'success',
            'data': serializer.data,
        })
