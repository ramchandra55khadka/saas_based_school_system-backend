from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.core.mixins import TenantViewSet
from utils.permissions import IsAdminOrHOD

from .models import Parent, StudentGuardian
from .serializers import (
    ParentOnboardSerializer,
    ParentSerializer,
    StudentGuardianSerializer,
)


class ParentViewSet(TenantViewSet):
    queryset = Parent.objects.select_related('user_profile')
    serializer_class = ParentSerializer
    permission_classes = [IsAuthenticated]

    # Parent writes (the regular create form and the single-dialog onboard)
    # are admin/HOD; reads stay open to every member.
    write_actions = ('create', 'update', 'partial_update', 'destroy', 'onboard')

    def get_permissions(self):
        if self.action in self.write_actions:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='onboard')
    def onboard(self, request):
        """Create a parent plus the user account and profile it needs.

        POST /api/parents/parents/onboard/ takes the account, personal-detail
        and parent-record fields flattened into one payload and writes the
        ``UserAccount``, ``UserProfile``, ``TenantMembership`` and ``Parent``
        rows in a single transaction - see ``ParentOnboardSerializer``.
        """
        serializer = ParentOnboardSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'tenant': self.require_tenant()},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StudentGuardianViewSet(TenantViewSet):
    queryset = StudentGuardian.objects.select_related('student', 'parent')
    serializer_class = StudentGuardianSerializer