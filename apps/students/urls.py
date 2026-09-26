from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StudentViewSet, StudentDocumentViewSet,
    StudentAttendanceViewSet, ExamViewSet,
    ExamResultViewSet, StudentPromotionViewSet,
)

router = DefaultRouter()
router.register(r'profiles', StudentViewSet, basename='student-profile')
router.register(r'documents', StudentDocumentViewSet, basename='student-document')
router.register(r'attendance', StudentAttendanceViewSet, basename='student-attendance')
router.register(r'exams', ExamViewSet, basename='exam')
router.register(r'results', ExamResultViewSet, basename='exam-result')
router.register(r'promotions', StudentPromotionViewSet, basename='student-promotion')

urlpatterns = [
    path('', include(router.urls)),
]
