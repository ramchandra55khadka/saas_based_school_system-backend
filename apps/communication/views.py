from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.core.mixins import TenantViewSet
from apps.students.models import Student
from apps.subscription.constants import FeatureKey
from apps.subscription.entitlements import HasFeatureAccess
from apps.teachers.models import Teacher
from utils.permissions import IsAdminOrHOD, IsTeacher, get_membership_role
from .models import StudentPost, TeacherAnnouncement, Announcement, Message, Notification
from .permissions import IsAuthorOrSchoolAdmin
from .serializers import (
    StudentPostSerializer, TeacherAnnouncementSerializer,
    AnnouncementSerializer, MessageSerializer, NotificationSerializer
)

# Actions where the object-level author/moderator check applies.
MODERATED_ACTIONS = ('update', 'partial_update', 'destroy')


def _resolve_or_400(model, lookup, user, tenant, field, message):
    """Fetch the caller's tenant-scoped ``model`` row or fail with a clear 400.

    A user with the right *role* but no linked ``Student``/``Teacher`` row
    used to hit an unhandled error; this turns it into a message the UI toast
    can show verbatim. ``lookup`` is the path from ``model`` to the caller's
    user account, e.g. ``user_profile__user_account``.
    """
    try:
        return model.objects.get(**{lookup: user, 'tenant': tenant})
    except model.DoesNotExist:
        raise ValidationError({field: message})


class StudentPostViewSet(TenantViewSet):
    queryset = StudentPost.objects.all()
    serializer_class = StudentPostSerializer
    feature_key = FeatureKey.COMMUNICATION
    permission_classes = [IsAuthenticated, HasFeatureAccess]

    def get_permissions(self):
        if self.action in MODERATED_ACTIONS:
            return [IsAuthenticated(), HasFeatureAccess(), IsAuthorOrSchoolAdmin()]
        return [IsAuthenticated(), HasFeatureAccess()]

    def perform_create(self, serializer):
        if get_membership_role(self.request.user, self.request.tenant) != 'student':
            raise PermissionDenied('Only students can create student posts.')
        # ``student`` is read-only in the serializer: link the caller's own
        # record (never a client-supplied id) so posts cannot be forged.
        student = _resolve_or_400(
            Student, 'user_profile__user_account',
            self.request.user, self.request.tenant, 'student',
            'No student record is linked to your account yet.',
        )
        with transaction.atomic():
            instance = serializer.save(student=student, tenant=self.request.tenant)
            self._validate_instance(instance)

class TeacherAnnouncementViewSet(TenantViewSet):
    queryset = TeacherAnnouncement.objects.all()
    serializer_class = TeacherAnnouncementSerializer
    feature_key = FeatureKey.COMMUNICATION
    permission_classes = [IsAuthenticated, HasFeatureAccess]

    def get_permissions(self):
        if self.action in MODERATED_ACTIONS:
            return [IsAuthenticated(), HasFeatureAccess(), IsAuthorOrSchoolAdmin()]
        return [IsAuthenticated(), HasFeatureAccess()]

    def perform_create(self, serializer):
        role = get_membership_role(self.request.user, self.request.tenant)
        if role not in ('teacher', 'hod', 'principal'):
            raise PermissionDenied('Only teaching staff can create teacher announcements.')
        teacher = _resolve_or_400(
            Teacher, 'staff__user_profile__user_account',
            self.request.user, self.request.tenant, 'teacher',
            'No teaching record is linked to your account yet.',
        )
        with transaction.atomic():
            instance = serializer.save(teacher=teacher, tenant=self.request.tenant)
            self._validate_instance(instance)

class AnnouncementViewSet(TenantViewSet):
    """Admin broadcasts announcements."""
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    feature_key = FeatureKey.COMMUNICATION
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_super_admin():
            return qs
        role = get_membership_role(user, self.request.tenant)
        if role in ['admin', 'hod']:
            return qs
        # Basic filtering: Everyone sees 'all', role-specific sees theirs
        if role == 'teacher':
            return qs.filter(target_audience__in=['all', 'teachers'])
        if role == 'student':
            return qs.filter(target_audience__in=['all', 'students'])
        if role == 'parent':
            return qs.filter(target_audience__in=['all', 'parents'])
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHOD(), HasFeatureAccess()]
        return [IsAuthenticated(), HasFeatureAccess()]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user, tenant=self.request.tenant)

class MessageViewSet(TenantViewSet):
    """Direct messaging."""
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    feature_key = FeatureKey.COMMUNICATION
    permission_classes = [IsAuthenticated, HasFeatureAccess]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        return qs.filter(recipient=user) | qs.filter(sender=user)

    def perform_create(self, serializer):
        recipient = serializer.validated_data.get('recipient')
        if recipient and not recipient.memberships.filter(
            tenant=self.request.tenant, is_active=True
        ).exists():
            raise ValidationError({
                'recipient': 'Recipient is not an active member of this school.'
            })
        serializer.save(sender=self.request.user, tenant=self.request.tenant)
        
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        msg = self.get_object()
        if msg.recipient == request.user:
            msg.is_read = True
            msg.save()
            return Response({"status": "marked as read"})
        return Response({"error": "Unauthorized"}, status=403)

class NotificationViewSet(TenantViewSet):
    """System notifications for users."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    feature_key = FeatureKey.COMMUNICATION
    permission_classes = [IsAuthenticated, HasFeatureAccess]

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        # ``user`` is read-only, so without this the row could not be created
        # (NOT NULL violation -> 500). Notifications are self-targeted.
        serializer.save(user=self.request.user, tenant=self.request.tenant)
        
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response({"status": "marked as read"})
