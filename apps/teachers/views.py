from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.mixins import TenantViewSet
from utils.permissions import IsAdminOrHOD, IsAdminOrHODOrTeacher, IsTeacher, get_membership_role
from apps.academics.models import TeacherAssignment, TimetableEntry
from apps.academics.serializers import TeacherAssignmentSerializer, TimetableEntrySerializer
from .models import Teacher, TeacherAttendance, LeaveRequest
from .serializers import (
    TeacherSerializer, TeacherAttendanceSerializer,
    LeaveRequestSerializer, TeacherOnboardSerializer,
)


class TeacherViewSet(TenantViewSet):
    """Teacher profile management. Admin manages all, teachers view own."""
    queryset = Teacher.objects.select_related(
        'staff', 'staff__user_profile__user_account'
    ).all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAuthenticated]

    # Same roles as staff management: reads stay open to every member because
    # attendance/leave screens list teachers too.
    write_actions = ('create', 'update', 'partial_update', 'destroy', 'onboard')

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if get_membership_role(user, self.request.tenant) == 'teacher':
            return qs.filter(staff__user_profile__user_account=user)
        return qs

    def get_permissions(self):
        if self.action in self.write_actions:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='onboard')
    def onboard(self, request):
        """Create a teacher plus the staff member, account and profile it needs.

        POST /api/teachers/profiles/onboard/ takes the account, personal-detail,
        employment and teaching fields flattened into one payload and writes the
        ``UserAccount``, ``UserProfile``, ``TenantMembership``, ``Staff`` and
        ``Teacher`` rows in a single transaction - see
        ``TeacherOnboardSerializer``.
        """
        serializer = TeacherOnboardSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'tenant': self.require_tenant()},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='assigned-classes')
    def assigned_classes(self, request, pk=None):
        """Get classes/sections assigned to this teacher."""
        profile = self.get_object()
        assignments = TeacherAssignment.objects.filter(
            teacher=profile.staff.user_profile.user_account,
            tenant=self.request.tenant,
        ).select_related('subject', 'section', 'academic_year')
        serializer = TeacherAssignmentSerializer(assignments, many=True)
        return Response({'status': 'success', 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='timetable')
    def timetable(self, request, pk=None):
        """Get timetable for this teacher."""
        profile = self.get_object()
        entries = TimetableEntry.objects.filter(
            teacher=profile.staff.user_profile.user_account,
            tenant=self.request.tenant,
        ).select_related('section', 'subject', 'academic_year')
        serializer = TimetableEntrySerializer(entries, many=True)
        return Response({'status': 'success', 'data': serializer.data})


class TeacherAttendanceViewSet(TenantViewSet):
    """Teacher attendance. Admin marks, teachers view own."""
    queryset = TeacherAttendance.objects.select_related(
        'teacher', 'teacher__staff__user_profile'
    ).all()
    serializer_class = TeacherAttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if get_membership_role(user, self.request.tenant) == 'teacher':
            return qs.filter(teacher__staff__user_profile__user_account=user)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]


class LeaveRequestViewSet(TenantViewSet):
    """Leave requests. Teachers create, Admin/HOD approve/reject."""
    queryset = LeaveRequest.objects.select_related(
        'teacher', 'teacher__staff__user_profile', 'approved_by'
    ).all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if get_membership_role(user, self.request.tenant) == 'teacher':
            return qs.filter(teacher__staff__user_profile__user_account=user)
        return qs

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsTeacher()]
        if self.action in ['approve', 'reject', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Auto-assign the teacher profile and the active tenant."""
        staff_record = getattr(getattr(self.request.user, 'profile', None), 'staff', None)
        profile = staff_record.teachers.first() if staff_record else None
        if profile is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('No teacher profile found for this user.')
        # LeaveRequest inherits the tenant field from AbstractTenantModel;
        # without it the INSERT violates the NOT NULL constraint.
        serializer.save(teacher=profile, tenant=self.request.tenant)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """Admin/HOD approves a leave request."""
        leave = self.get_object()
        leave.status = 'approved'
        leave.approved_by = request.user
        leave.responded_at = timezone.now()
        leave.save()
        return Response({
            'status': 'success',
            'message': 'Leave request approved.',
        })

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Admin/HOD rejects a leave request."""
        leave = self.get_object()
        leave.status = 'rejected'
        leave.approved_by = request.user
        leave.responded_at = timezone.now()
        leave.save()
        return Response({
            'status': 'success',
            'message': 'Leave request rejected.',
        })
