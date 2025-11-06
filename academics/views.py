from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from core.mixins import TenantViewSet
# from core.mixins import TenantViewSet imports a reusable base view class that handles tenant logic automatically.
# It ensures all queries are filtered by the current tenant and assigns request.tenant on create.
# This prevents cross-tenant data leaks and keeps your views clean and DRY.


from core.permissions import IsAdminOrHOD
from .models import Course, Subject, StudentRecord
from .serializers import CourseSerializer, SubjectSerializer, StudentRecordSerializer


# ------------------ COURSE -------------------
class CourseViewSet(TenantViewSet):
#CourseViewSet(TenantViewSet) automatically handles:

# Tenant Isolation
# → Filters all queries to request.tenant
# → No cross-tenant data leaks
# Auto-tenant on Create
# → perform_create() → serializer.save(tenant=request.tenant)
# Built-in Authentication
# → permission_classes = [IsAuthenticated]
# Clean CRUD
# → Full ModelViewSet behavior: list, retrieve, create, update, delete
    """
    Courses are tenant-scoped.
    - Admin/HOD can create courses.
    - All authenticated users in tenant can view.
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ["admin", "hod"]:
            raise PermissionDenied("Only Admin or HOD can create courses.")
        serializer.save(created_by=user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Courses retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "status": "success",
            "message": "Course created successfully.",
            "data": response.data
        }, status=status.HTTP_201_CREATED)


# ------------------ SUBJECT -------------------
class SubjectViewSet(TenantViewSet):
    """
    Subjects are tenant-scoped.
    - Admin/HOD can create.
    - All authenticated users can list.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHOD]

    def get_queryset(self):
        return super().get_queryset()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Subjects retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "status": "success",
            "message": "Subject created successfully.",
            "data": response.data
        }, status=status.HTTP_201_CREATED)


# ------------------ STUDENT RECORDS -------------------
class StudentRecordViewSet(TenantViewSet):
    """
    Student records are tenant-scoped.
    - Admin/HOD can create/update.
    - Students can only view their own.
    """
    queryset = StudentRecord.objects.all()
    serializer_class = StudentRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "student":
            return qs.filter(student=user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ["admin", "hod"]:
            raise PermissionDenied("Only Admin or HOD can create student records.")

        student = serializer.validated_data.get("student")
        course = serializer.validated_data.get("course")

        # Ensure both belong to same tenant
        if student.tenant != self.request.tenant or course.tenant != self.request.tenant:
            raise ValidationError("Student and Course must belong to the same tenant.")
        serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({
                "status": "error",
                "message": "No student records found."
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Student records retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "status": "success",
            "message": "Student record created successfully.",
            "data": response.data
        }, status=status.HTTP_201_CREATED)
