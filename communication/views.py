from rest_framework import generics, permissions
from .models import StudentPost, TeacherAnnouncement
from .serializers import StudentPostSerializer, TeacherAnnouncementSerializer
from .permissions import IsStudentOnlyPost,IsTeacherOnlyPost


# 🧑‍🎓 Student Post View
class StudentPostListCreateView(generics.ListCreateAPIView):
    serializer_class = StudentPostSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudentOnlyPost]

    def get_queryset(self):
        # Everyone (teacher, student, admin) can see student posts from their org
        user = self.request.user
        return StudentPost.objects.filter(organization=user.organization)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(organization=user.organization, student=user)


# 👨‍🏫 Teacher Announcement View
class TeacherAnnouncementListCreateView(generics.ListCreateAPIView):
    serializer_class = TeacherAnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOnlyPost]

    def get_queryset(self):
        user = self.request.user

        if user.role == "student":
            # Students see all announcements in their org
            return TeacherAnnouncement.objects.filter(organization=user.organization)

        elif user.role == "teacher":
            # Teachers see only their own announcements
            return TeacherAnnouncement.objects.filter(organization=user.organization, teacher=user)

        else:
            # Admins/HODs can read all announcements
            return TeacherAnnouncement.objects.filter(organization=user.organization)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(organization=user.organization, teacher=user)
