"""URLs for the user_account app, mounted once at ``/api/``.

Two groups live here:

* ``auth/``    — login, refresh, logout. Login is the only genuinely
  context-dependent endpoint, so it is split in two: ``auth/login/`` is tenant
  login and requires a school subdomain, while ``auth/super-user/login/`` is
  the platform-host-only super-admin counterpart. ``auth/refresh/`` and
  ``auth/logout/`` are shared by both, because both operate purely on the
  refresh cookie and :func:`apps.user_account.views.validate_refresh_context`
  already re-checks the host against the token's tenant claim.
* ``accounts/`` — everything else: ``me``, ``user-management``,
  ``member-directory`` and super-admin tenant onboarding.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CookieTokenRefreshView,
    LogoutView,
    MemberDirectoryView,
    MeView,
    SuperAdminLoginView,
    SuperAdminTenantCreateView,
    TenantLoginView,
    UserManagementViewSet,
)

router = DefaultRouter()
router.register(r'user-management', UserManagementViewSet, basename='user-management')

urlpatterns = [
    # ── Authentication ──────────────────────────────────────────────────
    path('auth/login/', TenantLoginView.as_view(), name='auth_login'),
    path('auth/super-user/login/', SuperAdminLoginView.as_view(), name='super_user_login'),
    path('auth/refresh/', CookieTokenRefreshView.as_view(), name='auth_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),

    # ── Accounts ────────────────────────────────────────────────────────
    path('accounts/me/', MeView.as_view(), name='me'),
    path('accounts/member-directory/', MemberDirectoryView.as_view(), name='member-directory'),
    path('accounts/superadmin/create-tenant/', SuperAdminTenantCreateView.as_view(), name='superadmin-create-tenant'),
    path('accounts/', include(router.urls)),
]
