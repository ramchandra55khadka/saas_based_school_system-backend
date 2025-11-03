from rest_framework import serializers
from .models import StudentPost, TeacherAnnouncement


class StudentPostSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.username", read_only=True)

    class Meta:
        model = StudentPost
        fields = ["id", "organization", "student", "student_name", "title", "content", "created_at"]
        read_only_fields = ["organization", "student", "created_at"]


class TeacherAnnouncementSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.username", read_only=True)

    class Meta:
        model = TeacherAnnouncement
        fields = ["id", "organization", "teacher", "teacher_name", "title", "content", "created_at"]
        read_only_fields = ["organization", "teacher", "created_at"]
