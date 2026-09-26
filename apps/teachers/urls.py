from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TeacherViewSet, TeacherAttendanceViewSet,
    LeaveRequestViewSet,
)

router = DefaultRouter()
router.register(r'profiles', TeacherViewSet, basename='teacher-profile')
router.register(r'attendance', TeacherAttendanceViewSet, basename='teacher-attendance')
router.register(r'leave-requests', LeaveRequestViewSet, basename='leave-request')

urlpatterns = [
    path('', include(router.urls)),
]
