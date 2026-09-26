from rest_framework import serializers
from .models import StudentPost, TeacherAnnouncement, Announcement, Message, Notification


def account_full_name(user):
    profile = getattr(user, 'profile', None)
    if profile is None:
        return user.username
    return f'{profile.first_name} {profile.last_name}'.strip() or user.username


class StudentPostSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user_profile', read_only=True)
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = StudentPost
        fields = ['id', 'tenant', 'student', 'student_name', 'is_author', 'title', 'content', 'created_at']
        # ``student`` is server-assigned: perform_create links the caller's own
        # Student record, so a client can never post as someone else.
        read_only_fields = ['id', 'tenant', 'student', 'created_at']

    def get_is_author(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        return obj.student.user_profile.user_account_id == user.id


class TeacherAnnouncementSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.staff.user_profile', read_only=True)
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = TeacherAnnouncement
        fields = ['id', 'tenant', 'teacher', 'teacher_name', 'is_author', 'title', 'content', 'created_at']
        # ``teacher`` is server-assigned for the same reason as ``student``.
        read_only_fields = ['id', 'tenant', 'teacher', 'created_at']

    def get_is_author(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        return obj.teacher.staff.user_profile.user_account_id == user.id

class AnnouncementSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'tenant', 'sender', 'sender_name', 'target_audience', 'title', 'content', 'created_at']
        read_only_fields = ['id', 'tenant', 'sender', 'created_at']

    def get_sender_name(self, obj):
        return account_full_name(obj.sender)

class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'tenant', 'sender', 'sender_name', 'recipient', 'recipient_name', 'subject', 'content', 'is_read', 'created_at']
        read_only_fields = ['id', 'tenant', 'sender', 'is_read', 'created_at']

    def get_sender_name(self, obj):
        return account_full_name(obj.sender)

    def get_recipient_name(self, obj):
        return account_full_name(obj.recipient)

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'tenant', 'user', 'title', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'tenant', 'user', 'created_at']
