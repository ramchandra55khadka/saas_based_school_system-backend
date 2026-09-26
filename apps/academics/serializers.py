from rest_framework import serializers
from .models import (
    AcademicYear, Class, Section, Subject,
    TeacherAssignment, TimetableEntry,
)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = [
            'id', 'tenant', 'name', 'start_date', 'end_date',
            'is_current', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = [
            'id', 'tenant', 'name', 'numeric_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class SectionSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='school_class.name', read_only=True)

    class Meta:
        model = Section
        fields = [
            'id', 'tenant', 'name', 'school_class', 'class_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    """Subject with the classes that offer it (M2M)."""
    class_names = serializers.SerializerMethodField()
    school_classes = serializers.PrimaryKeyRelatedField(
        queryset=Class.objects.all(), many=True, required=False, allow_empty=True,
        help_text="Classes that offer this subject; must belong to this school.",
    )

    class Meta:
        model = Subject
        fields = [
            'id', 'tenant', 'name', 'code', 'credit_hours',
            'is_optional', 'school_classes', 'class_names',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def get_class_names(self, obj):
        return list(
            obj.school_classes.order_by('numeric_name').values_list('name', flat=True)
        )

    def validate_school_classes(self, value):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        if tenant is not None:
            for school_class in value:
                if school_class.tenant_id != tenant.pk:
                    raise serializers.ValidationError(
                        "Subjects can only be linked to classes in this school."
                    )
        return value


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.__str__', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    section_name = serializers.CharField(source='section.__str__', read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = [
            'id', 'tenant', 'teacher', 'teacher_name',
            'subject', 'subject_name', 'section', 'section_name',
            'academic_year', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class TimetableEntrySerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.__str__', read_only=True)
    section_name = serializers.CharField(source='section.__str__', read_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'tenant', 'section', 'section_name',
            'subject', 'subject_name', 'teacher', 'teacher_name',
            'academic_year', 'day_of_week', 'period_number',
            'start_time', 'end_time', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
