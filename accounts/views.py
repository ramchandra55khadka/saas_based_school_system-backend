
from django.conf import settings
from rest_framework import generics, status,viewsets
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import SignupSerializer, OrganizationSerializer, UserSerializer
from .permissions import IsSuperAdmin, IsAdminOrHod, IsAdminOrHodUserManagement

User = get_user_model()


# --------------------------------
# Super-admin: Create Organization + Initial Admin
# --------------------------------
class SuperAdminOrganizationCreateView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, *args, **kwargs):
        org_data = request.data.get("organization")
        admin_data = request.data.get("admin_user")

        # Create Organization
        org_serializer = OrganizationSerializer(data=org_data)
        org_serializer.is_valid(raise_exception=True)
        org = org_serializer.save()

        # Create initial admin
        admin_data["organization"] = org.id
        admin_data["role"] = "admin"
        user_serializer = UserSerializer(data=admin_data)
        user_serializer.is_valid(raise_exception=True)
        user_serializer.save()

        return Response({
            "message": "Organization and initial admin created successfully",
            "organization": org_serializer.data,
            "admin_user": user_serializer.data
        }, status=status.HTTP_201_CREATED)


class UserManagementViewSet(viewsets.ModelViewSet):
    """
    Admin/HOD can manage users based on role.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHodUserManagement]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return User.objects.filter(organization=user.organization)
        elif user.role == "hod":
            return User.objects.filter(organization=user.organization, role__in=["teacher", "student"])
        else:
            return User.objects.none()  # no access
        
        

    def perform_create(self, serializer):
        creator = self.request.user
        role = serializer.validated_data.get("role")

        # Role validation
        if creator.role == "admin":
            allowed_roles = ["hod", "teacher", "student"]
        elif creator.role == "hod":
            allowed_roles = ["teacher", "student"]
        else:
            allowed_roles = []

        if role not in allowed_roles:
            raise PermissionError(f"{creator.role} cannot create a user with role '{role}'")

        serializer.save(organization=creator.organization)

# --------------------------------
# JWT Login with HttpOnly Cookies
# --------------------------------
class CookieTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            access = data.get("access")
            refresh = data.get("refresh")

            resp = Response({"message": "Login successful","access_token":access,"refresh_token":refresh}, status=200)
            resp.set_cookie(settings.JWT_ACCESS_COOKIE, access, httponly=True, samesite="Lax")
            resp.set_cookie(settings.JWT_REFRESH_COOKIE, refresh, httponly=True, samesite="Lax")
            return resp
        return response