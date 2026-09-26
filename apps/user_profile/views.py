from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import UserProfile
from .serializers import UserProfileSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related('user_account')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

