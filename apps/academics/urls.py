from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AcademicYearViewSet, ClassViewSet, SectionViewSet,
    SubjectViewSet, TeacherAssignmentViewSet, TimetableEntryViewSet,
)

router = DefaultRouter()
router.register(r'academic-years', AcademicYearViewSet, basename='academic-year')
router.register(r'classes', ClassViewSet, basename='class')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'teacher-assignments', TeacherAssignmentViewSet, basename='teacher-assignment')
router.register(r'timetable', TimetableEntryViewSet, basename='timetable')

urlpatterns = [
    path('', include(router.urls)),
]
