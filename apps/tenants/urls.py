from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SchoolProfileViewSet, SchoolSettingsViewSet, DepartmentViewSet

router = DefaultRouter()
router.register(r'profile', SchoolProfileViewSet, basename='school-profile')
router.register(r'settings', SchoolSettingsViewSet, basename='school-settings')
router.register(r'departments', DepartmentViewSet, basename='department')

urlpatterns = [
    path('', include(router.urls)),
]
