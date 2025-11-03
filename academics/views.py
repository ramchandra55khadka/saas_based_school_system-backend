from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError
from .models import Course, Subject, StudentRecord
from .serializers import CourseSerializer, SubjectSerializer, StudentRecordSerializer
from accounts.permissions import IsAdminOrHod


# ------------------ COURSE -------------------
class CourseListCreateView(generics.ListCreateAPIView):
    """
    Course can be created by admin or HOD only, 
    but can be viewed by all authenticated users.
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Course.objects.filter(organization=self.request.user.organization)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Courses retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ["admin", "hod"]:
            raise PermissionDenied("Only Admin or HOD can create courses.")
        serializer.save(organization=user.organization, created_by=user)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "status": "success",
            "message": "Course created successfully.",
            "data": response.data
        }, status=status.HTTP_201_CREATED)


# ------------------ SUBJECT -------------------
class SubjectListCreateView(generics.ListCreateAPIView):
    """
    Subject can be created only by admin or HOD.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrHod]

    def get_queryset(self):
        return Subject.objects.filter(organization=self.request.user.organization)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Subjects retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=request.user.organization)
        return Response({
            "status": "success",
            "message": "Subject created successfully.",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)


# ------------------ STUDENT RECORDS -------------------
class StudentRecordListCreateView(generics.ListCreateAPIView):
    """
    Admin/HOD can create student records (grades).
    Students can only view their own.
    """
    serializer_class = StudentRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "student":
            return StudentRecord.objects.filter(student=user)
        return StudentRecord.objects.filter(organization=user.organization)

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

    def perform_create(self, serializer):
        user = self.request.user

        # Only admin or hod can create
        if user.role not in ["admin", "hod"]:
            raise PermissionDenied("Only Admin or HOD can create student records.")

        student = serializer.validated_data.get("student")
        course = serializer.validated_data.get("course")

        # Validate same organization
        if student.organization != user.organization or course.organization != user.organization:
            raise ValidationError("Student and Course must belong to the same organization as the creator.")

        serializer.save(organization=user.organization)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "status": "success",
            "message": "Student record created successfully.",
            "data": response.data
        }, status=status.HTTP_201_CREATED)