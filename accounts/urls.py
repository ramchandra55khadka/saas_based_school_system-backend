from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SuperAdminTenantCreateView,
    UserManagementViewSet,
    CookieTokenObtainPairView,
    LogoutView
)

router = DefaultRouter()
router.register(r'user-management', UserManagementViewSet, basename='user-management')

urlpatterns = [
    # JWT login/logout
    path('login/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Super-admin tenant creation
    path('superadmin/create-tenant/', SuperAdminTenantCreateView.as_view(), name='superadmin-create-tenant'),

    # User management routes via DRF router
    path('', include(router.urls)),
]
