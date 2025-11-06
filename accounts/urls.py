from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import SuperAdminTenantCreateView, UserManagementViewSet,CookieTokenObtainPairView,LogoutView

# Create DRF router for UserManagementViewSet
router = DefaultRouter()
router.register(r'user-management', UserManagementViewSet, basename='user-management')

urlpatterns = [
    # Super-admin: create org + initial admin
    path("superadmin/create-tenant/", SuperAdminTenantCreateView.as_view(), name="superadmin_create_org"),

    # JWT login
    path("login/", CookieTokenObtainPairView.as_view(), name="login"),
    path("logout/",LogoutView.as_view(), name="logout"),

    #  JWT refresh endpoint (reads refresh cookie or body)
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Include router URLs for UserManagementViewSet
    path("", include(router.urls)),
]
