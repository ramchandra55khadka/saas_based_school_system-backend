from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StudentPostViewSet, TeacherAnnouncementViewSet,
    AnnouncementViewSet, MessageViewSet, NotificationViewSet
)

router = DefaultRouter()
router.register(r'student-posts', StudentPostViewSet, basename='student-post')
router.register(r'teacher-announcements', TeacherAnnouncementViewSet, basename='teacher-announcement')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]
