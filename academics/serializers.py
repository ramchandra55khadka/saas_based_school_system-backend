from rest_framework import serializers
from .models import Course, Subject, StudentRecord


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = "__all__"
        read_only_fields = ["created_by","created_at","organization"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"
        read_only_fields = ["organization"]



class StudentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentRecord
        fields = "__all__"
        read_only_fields = ["created_at","organization"]
