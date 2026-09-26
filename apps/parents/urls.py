from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ParentViewSet, StudentGuardianViewSet

router = DefaultRouter()
router.register(r'parents', ParentViewSet, basename='parent')
router.register(r'guardians', StudentGuardianViewSet, basename='student-guardian')

urlpatterns = [
    path('', include(router.urls)),
]
