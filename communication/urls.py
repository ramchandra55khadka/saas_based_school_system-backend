from django.urls import path
from .views import StudentPostListCreateView, TeacherAnnouncementListCreateView

urlpatterns = [
    path("student-posts/", StudentPostListCreateView.as_view(), name="student-posts"),
    path("teacher-announcements/", TeacherAnnouncementListCreateView.as_view(), name="teacher-announcements"),
]
