# communications/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentPostViewSet, TeacherAnnouncementViewSet

# DRF router automatically creates routes for ViewSets
router = DefaultRouter()
router.register(r'student-posts', StudentPostViewSet, basename='student-posts')
router.register(r'teacher-announcements', TeacherAnnouncementViewSet, basename='teacher-announcements')

urlpatterns = [
    path('', include(router.urls)),
]
