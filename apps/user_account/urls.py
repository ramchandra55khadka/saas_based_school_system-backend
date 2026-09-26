from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SuperAdminTenantCreateView,
    UserManagementViewSet,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    MeView,
    MemberDirectoryView,
)

router = DefaultRouter()
router.register(r'user-management', UserManagementViewSet, basename='user-management')

urlpatterns = [
    path('login/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('member-directory/', MemberDirectoryView.as_view(), name='member-directory'),
    path('superadmin/create-tenant/', SuperAdminTenantCreateView.as_view(), name='superadmin-create-tenant'),
    path('', include(router.urls)),
]
