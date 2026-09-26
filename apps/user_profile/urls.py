from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserProfileViewSet

router = DefaultRouter()
router.register(r'profiles', UserProfileViewSet, basename='user-profile')

urlpatterns = [
    path('', include(router.urls)),
]

