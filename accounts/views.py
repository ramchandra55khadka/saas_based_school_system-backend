
# # accounts/views.py
# from django.conf import settings
# from rest_framework.views import APIView
# from rest_framework import generics, viewsets, status, serializers
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from rest_framework_simplejwt.views import TokenObtainPairView
# from rest_framework_simplejwt.tokens import RefreshToken

# from .serializers import UserSerializer, SignupSerializer
# from core.mixins import TenantRequiredMixin, TenantViewSet
# from core.permissions import IsSuperAdmin, IsAdminOrHodUserManagement
# from accounts.models import TenantMembership, RoleChoices
# from django.contrib.auth import get_user_model

# User = get_user_model()


# # -----------------------------
# # Super-admin: Create Tenant + Initial Admin
# # -----------------------------
# class SuperAdminTenantCreateView(TenantRequiredMixin, generics.CreateAPIView):
#     """
#     Super-admin can create a new tenant along with its initial admin user.
#     """
#     serializer_class = SignupSerializer
#     permission_classes = [IsAuthenticated, IsSuperAdmin]

#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         result = serializer.save()
#         return Response({
#             "message": "Tenant and initial admin created successfully",
#             "tenant": {
#                 "tenant_id": result["tenant"].tenant_id,
#                 "tenant_name": result["tenant"].tenant_name,
#                 "org_code": result["tenant"].org_code,
#             },
#             "admin_user": {
#                 "id": result["admin_user"].id,
#                 "username": result["admin_user"].username,
#                 "email": result["admin_user"].email,
#                 "role": result["admin_user"].role,
#             }
#         }, status=status.HTTP_201_CREATED)


# # -----------------------------
# # User Management ViewSet
# # -----------------------------
# class UserManagementViewSet(TenantViewSet):
#     """
#     Tenant-scoped user management.
#     - Admin: manage all users.
#     - HOD: manage teachers and students.
#     Clean JSON responses with tenant info included.
#     """
#     serializer_class = UserSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrHodUserManagement]

#     def get_queryset(self):
#         user = self.request.user
#         tenant = getattr(self.request, "tenant", None)
#         qs = super().get_queryset() if hasattr(super(), "get_queryset") else User.objects.all()

#         if not tenant:
#             return User.objects.none()

#         qs = qs.filter(tenantmembership__tenant=tenant)

#         if user.role == RoleChoices.ADMIN:
#             return qs
#         elif user.role == RoleChoices.HOD:
#             return qs.filter(role__in=[RoleChoices.TEACHER, RoleChoices.STUDENT])
#         return qs.none()

#     def create(self, request, *args, **kwargs):
#         tenant = getattr(request, "tenant", None)
#         if not tenant:
#             return Response(
#                 {"message": "Tenant context missing. Make sure you are logged in with a valid tenant token."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         creator = request.user
#         role = serializer.validated_data.get("role")

#         # Role-based restrictions
#         allowed = {
#             RoleChoices.ADMIN: [RoleChoices.HOD, RoleChoices.TEACHER, RoleChoices.STUDENT],
#             RoleChoices.HOD: [RoleChoices.TEACHER, RoleChoices.STUDENT],
#         }.get(creator.role, [])

#         if role not in allowed:
#             return Response(
#                 {"message": f"{creator.role} cannot create user with role '{role}'"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         user = serializer.save()
#         TenantMembership.objects.create(
#             user=user,
#             tenant=tenant,
#             role=role,
#             is_active=True
#         )

#         return Response(
#             {
#                 "message": "User created successfully.",
#                 "tenant": {
#                     "tenant_id": str(tenant.tenant_id),
#                     "tenant_name": tenant.tenant_name,
#                 },
#                 "user": {
#                     "id": user.id,
#                     "username": user.username,
#                     "email": user.email,
#                     "role": user.role,
#                 },
#             },
#             status=status.HTTP_201_CREATED,
#         )


# # -----------------------------
# # JWT Login + HttpOnly Cookies
# # -----------------------------
# class CookieTokenObtainPairView(TokenObtainPairView):
#     """
#     Custom JWT login view for super-admin / tenant users.
#     Sets access + refresh tokens in HttpOnly cookies and includes tenant claim.
#     """
#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.user  # ✅ Authenticated user

#         # Generate tokens
#         refresh = RefreshToken.for_user(user)
#         access = refresh.access_token

#         # Add tenant claim (skip for super-admin)
#         if not getattr(user, "is_super_admin", False):
#             membership = TenantMembership.objects.filter(
#                 user=user, is_active=True
#             ).select_related("tenant").first()
#             if membership:
#                 tenant_id = str(membership.tenant.tenant_id)
#                 access["active_tenant_id"] = tenant_id
#                 refresh["active_tenant_id"] = tenant_id

#         # Build response
#         resp = Response({
#             "message": "Login successful",
#             "access_token": str(access),
#             "refresh_token": str(refresh),
#         })

#         # Set HttpOnly cookies
#         resp.set_cookie(
#             settings.JWT_ACCESS_COOKIE, str(access),
#             httponly=True, samesite="Lax", secure=not settings.DEBUG
#         )
#         resp.set_cookie(
#             settings.JWT_REFRESH_COOKIE, str(refresh),
#             httponly=True, samesite="Lax", secure=not settings.DEBUG
#         )

#         return resp


# # -----------------------------
# # Logout
# # -----------------------------
# class LogoutView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         response = Response({"message": "Logout successful"}, status=200)
#         response.delete_cookie(settings.JWT_ACCESS_COOKIE, samesite="Lax")
#         response.delete_cookie(settings.JWT_REFRESH_COOKIE, samesite="Lax")
#         return response

# accounts/views.py
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import UserSerializer, SignupSerializer
from core.mixins import TenantViewSet
from core.permissions import IsSuperAdmin, IsAdminOrHodUserManagement
from accounts.models import TenantMembership, RoleChoices

User = get_user_model()


# -----------------------------
# Super Admin: Create Tenant + Initial Admin
# -----------------------------
class SuperAdminTenantCreateView(generics.CreateAPIView):
    """
    Super admin creates a new tenant + initial admin.
    Skipped by TenantRequiredMixin (in PUBLIC_PATHS).
    """
    serializer_class = SignupSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


# -----------------------------
# User Management ViewSet
# -----------------------------
class UserManagementViewSet(TenantViewSet):
    """
    Tenant-scoped user management.
    - TenantRequiredMixin → sets request.tenant
    - TenantQuerysetMixin → filters by tenant
    - TenantViewSet → auto-filters queryset
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHodUserManagement]

    def get_queryset(self):
        """
        Filter users by role permissions.
        Base queryset already filtered by tenant via TenantQuerysetMixin.
        """
        user = self.request.user
        qs = super().get_queryset()

        if user.role == RoleChoices.ADMIN:
            return qs
        elif user.role == RoleChoices.HOD:
            return qs.filter(role__in=[RoleChoices.TEACHER, RoleChoices.STUDENT])
        return qs.none()

    def perform_create(self, serializer):
        """
        Validate role + create TenantMembership.
        request.tenant is guaranteed by TenantRequiredMixin.
        """
        creator = self.request.user
        role = serializer.validated_data.get("role")

        # Role validation
        allowed_roles = {
            RoleChoices.ADMIN: [RoleChoices.HOD, RoleChoices.TEACHER, RoleChoices.STUDENT],
            RoleChoices.HOD: [RoleChoices.TEACHER, RoleChoices.STUDENT],
        }.get(creator.role, [])

        if role not in allowed_roles:
            raise serializers.ValidationError(
                f"{creator.role} cannot create a user with role '{role}'"
            )

        # Save user
        user = serializer.save()

        # Link to current tenant
        TenantMembership.objects.create(
            user=user,
            tenant=self.request.tenant,
            role=role,
            is_active=True
        )


# -----------------------------
# JWT Login with HttpOnly Cookies + Tenant Claim
# -----------------------------
# accounts/views.py
class CookieTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # Add tenant claim
        if not user.is_super_admin():
            membership = TenantMembership.objects.filter(user=user, is_active=True).first()
            if membership:
                tenant_id = str(membership.tenant.tenant_id)
                access["active_tenant_id"] = tenant_id
                refresh["active_tenant_id"] = tenant_id  # Also add to refresh

        resp = Response({
            "message": "Login successful",
            "access_token": str(access),
            "refresh_token": str(refresh),
        })

        resp.set_cookie(settings.JWT_ACCESS_COOKIE, str(access), httponly=True, samesite="Lax", path="/")
        resp.set_cookie(settings.JWT_REFRESH_COOKIE, str(refresh), httponly=True, samesite="Lax", path="/")
        return resp
# -----------------------------
# Logout
# -----------------------------
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        response = Response({"message": "Logout successful"}, status=200)
        response.delete_cookie(settings.JWT_ACCESS_COOKIE, samesite="Lax", path="/")
        response.delete_cookie(settings.JWT_REFRESH_COOKIE, samesite="Lax", path="/")
        return response