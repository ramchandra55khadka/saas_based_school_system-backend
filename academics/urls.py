from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, SubjectViewSet, StudentRecordViewSet

# Router setup
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'student-records', StudentRecordViewSet, basename='student-record')

urlpatterns = [
    path('', include(router.urls)),
]
