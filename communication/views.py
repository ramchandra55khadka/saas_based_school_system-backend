
# Uses TenantViewSet → automatically filters by tenant and assigns it at creation.


# Keeps role-based creation logic clear (IsStudentOnlyPost, IsTeacherOnlyPost).


# Tenant isolation happens automatically — no organization field or cross-tenant risk.


from rest_framework import permissions
from core.mixins import TenantViewSet  # ✅ Automatically filters by tenant & assigns request.tenant ##vvimp
from .models import StudentPost, TeacherAnnouncement
from .serializers import StudentPostSerializer, TeacherAnnouncementSerializer
from .permissions import IsStudentOnlyPost, IsTeacherOnlyPost


# 🧑‍🎓 Student Post ViewSet
class StudentPostViewSet(TenantViewSet):
    """
    Tenant-aware ViewSet for student posts.
    - Only students can create posts.
    - All users in the tenant (teachers, admins, students) can view posts.
    """
    queryset = StudentPost.objects.all()
    serializer_class = StudentPostSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudentOnlyPost]

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(student=user)  # tenant auto-added by TenantViewSet


# 👨‍🏫 Teacher Announcement ViewSet
class TeacherAnnouncementViewSet(TenantViewSet):
    """
    Tenant-aware ViewSet for teacher announcements.
    - Only teachers can create announcements.
    - Students, teachers, and admins in the same tenant can view them.
    """
    queryset = TeacherAnnouncement.objects.all()
    serializer_class = TeacherAnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOnlyPost]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        if user.role == "student":
            return qs  # students see all announcements in their tenant
        elif user.role == "teacher":
            return qs.filter(teacher=user)
        else:
            return qs  # admins/HODs can see all

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(teacher=user)  # tenant auto-added by TenantViewSet
