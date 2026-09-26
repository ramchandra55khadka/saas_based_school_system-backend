from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import TenantViewSet
from utils.permissions import IsAdminOrHOD

from .models import Staff
from .serializers import StaffOnboardSerializer, StaffSerializer


class StaffViewSet(TenantViewSet):
    queryset = Staff.objects.select_related('user_profile', 'department')
    serializer_class = StaffSerializer

    # Roles that may manage staff (mirrors the ``manage_staff`` permission in
    # the frontend). Reads stay open to every member because the payroll and
    # library screens list staff too.
    write_actions = ('create', 'update', 'partial_update', 'destroy', 'onboard')

    def get_permissions(self):
        if self.action in self.write_actions:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return super().get_permissions()

    @action(detail=False, methods=['post'], url_path='onboard')
    def onboard(self, request):
        """Create a staff member plus the user account and profile it needs.

        POST /api/staff/staff/onboard/ takes the account, personal-detail and
        employment fields flattened into one payload and writes the
        ``UserAccount``, ``UserProfile``, ``TenantMembership`` and ``Staff`` rows
        in a single transaction - see ``StaffOnboardSerializer``.
        """
        serializer = StaffOnboardSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'tenant': self.require_tenant()},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
