from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SuperAdminOrganizationCreateView, CookieTokenObtainPairView, UserManagementViewSet

# Create DRF router for UserManagementViewSet
router = DefaultRouter()
router.register(r'user-management', UserManagementViewSet, basename='user-management')

urlpatterns = [
    # Super-admin: create org + initial admin
    path("superadmin/create-organization/", SuperAdminOrganizationCreateView.as_view(), name="superadmin_create_org"),

    # JWT login
    path("login/", CookieTokenObtainPairView.as_view(), name="login"),

    # Include router URLs for UserManagementViewSet
    path("", include(router.urls)),
]
