
# from django.conf import settings
# from rest_framework import generics, status,viewsets
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from django.contrib.auth import get_user_model
# from rest_framework_simplejwt.views import TokenObtainPairView
# from .serializers import SignupSerializer, OrganizationSerializer, UserSerializer
# from .permissions import IsSuperAdmin, IsAdminOrHod, IsAdminOrHodUserManagement

# User = get_user_model()


# # --------------------------------
# # Super-admin: Create Organization + Initial Admin
# # --------------------------------
# class SuperAdminOrganizationCreateView(generics.CreateAPIView):
#     serializer_class = SignupSerializer
#     permission_classes = [IsAuthenticated, IsSuperAdmin]

#     def post(self, request, *args, **kwargs):
#         org_data = request.data.get("organization")
#         admin_data = request.data.get("admin_user")

#         # Create Organization
#         org_serializer = OrganizationSerializer(data=org_data)
#         org_serializer.is_valid(raise_exception=True)
#         org = org_serializer.save()

#         # Create initial admin
#         admin_data["organization"] = org.id
#         admin_data["role"] = "admin"
#         user_serializer = UserSerializer(data=admin_data)
#         user_serializer.is_valid(raise_exception=True)
#         user_serializer.save()

#         return Response({
#             "message": "Organization and initial admin created successfully",
#             "organization": org_serializer.data,
#             "admin_user": user_serializer.data
#         }, status=status.HTTP_201_CREATED)


# class UserManagementViewSet(viewsets.ModelViewSet):
#     """
#     Admin/HOD can manage users based on role.
#     """
#     queryset = User.objects.all()
#     serializer_class = UserSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrHodUserManagement]

#     def get_queryset(self):
#         user = self.request.user
#         if user.role == "admin":
#             return User.objects.filter(organization=user.organization)
#         elif user.role == "hod":
#             return User.objects.filter(organization=user.organization, role__in=["teacher", "student"])
#         else:
#             return User.objects.none()  # no access
        
        

#     def perform_create(self, serializer):
#         creator = self.request.user
#         role = serializer.validated_data.get("role")

#         # Role validation
#         if creator.role == "admin":
#             allowed_roles = ["hod", "teacher", "student"]
#         elif creator.role == "hod":
#             allowed_roles = ["teacher", "student"]
#         else:
#             allowed_roles = []

#         if role not in allowed_roles:
#             raise PermissionError(f"{creator.role} cannot create a user with role '{role}'")

#         serializer.save(organization=creator.organization)

# # --------------------------------
# # JWT Login with HttpOnly Cookies
# # --------------------------------
# class CookieTokenObtainPairView(TokenObtainPairView):
#     def post(self, request, *args, **kwargs):
#         response = super().post(request, *args, **kwargs)
#         if response.status_code == 200:
#             data = response.data
#             access = data.get("access")
#             refresh = data.get("refresh")

#             resp = Response({"message": "Login successful","access_token":access,"refresh_token":refresh}, status=200)
#             resp.set_cookie(settings.JWT_ACCESS_COOKIE, access, httponly=True, samesite="Lax")
#             resp.set_cookie(settings.JWT_REFRESH_COOKIE, refresh, httponly=True, samesite="Lax")
#             return resp
#         return response


# accounts/views.py
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework import generics, viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import UserSerializer, SignupSerializer
from core.permissions import (
    IsSuperAdmin,
    IsAdminOrHodUserManagement,
)
from accounts.models import TenantMembership, RoleChoices

User = get_user_model()


# -----------------------------
# Super-admin: Create Tenant + Initial Admin
# -----------------------------
class SuperAdminTenantCreateView(generics.CreateAPIView):
    """
    Only super-admin can create new tenants along with initial admin.
    """
    serializer_class = SignupSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response({
            "message": "Tenant and initial admin created successfully",
            "tenant": {
                "tenant_id": result["tenant"].tenant_id,
                "tenant_name": result["tenant"].tenant_name,
                "org_code": result["tenant"].org_code,
            },
            "admin_user": {
                "id": result["admin_user"].id,
                "username": result["admin_user"].username,
                "email": result["admin_user"].email,
                "role": result["admin_user"].role,
            }
        }, status=status.HTTP_201_CREATED)


# -----------------------------
# User Management ViewSet
# -----------------------------
class UserManagementViewSet(viewsets.ModelViewSet):
    """
    Admin/HOD can manage users within their tenant.
    Admin: manage all users.
    HOD: manage only teacher/student.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHodUserManagement]

    def get_queryset(self):
        """
        Filter users to the current tenant only.
        """
        tenant = getattr(self.request, "tenant", None)
        user = self.request.user
        if not tenant:
            return User.objects.none()

        if user.role == RoleChoices.ADMIN:
            return User.objects.filter(
                memberships__tenant=tenant, memberships__is_active=True
            )
        elif user.role == RoleChoices.HOD:
            return User.objects.filter(
                memberships__tenant=tenant,
                memberships__is_active=True,
                role__in=[RoleChoices.TEACHER, RoleChoices.STUDENT]
            )
        return User.objects.none()

    def perform_create(self, serializer):
        """
        Auto-link created user to current tenant and validate role.
        """
        creator = self.request.user
        tenant = getattr(self.request, "tenant", None)
        role = serializer.validated_data.get("role")

        # Role validation
        if creator.role == RoleChoices.ADMIN:
            allowed_roles = [RoleChoices.HOD, RoleChoices.TEACHER, RoleChoices.STUDENT]
        elif creator.role == RoleChoices.HOD:
            allowed_roles = [RoleChoices.TEACHER, RoleChoices.STUDENT]
        else:
            allowed_roles = []

        if role not in allowed_roles:
            raise PermissionError(f"{creator.role} cannot create a user with role '{role}'")

        user = serializer.save()
        # Create TenantMembership for the user
        TenantMembership.objects.create(
            user=user,
            tenant=tenant,
            role=role,
            is_active=True
        )


# -----------------------------
# JWT Login with HttpOnly cookies
# -----------------------------
class CookieTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT login view that sets HttpOnly cookies.
    """
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            access = data.get("access")
            refresh = data.get("refresh")

            resp = Response({"message": "Login successful", "access_token": access, "refresh_token": refresh},status=200)
            # Set HttpOnly cookies
            resp.set_cookie(settings.JWT_ACCESS_COOKIE, access, httponly=True, samesite="Lax")
            resp.set_cookie(settings.JWT_REFRESH_COOKIE, refresh, httponly=True, samesite="Lax")

            return resp
        return response
    

#For Logout

class LogoutView(APIView):
    """
    Logs out user by deleting JWT cookies (access + refresh).
    Works with HttpOnly cookies set during login.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        response = Response({"message": "Logout successful"}, status=200)
        # Delete the cookies safely
        response.delete_cookie(settings.JWT_ACCESS_COOKIE, samesite="Lax")
        response.delete_cookie(settings.JWT_REFRESH_COOKIE, samesite="Lax")
        return response