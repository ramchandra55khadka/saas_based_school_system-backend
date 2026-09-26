from rest_framework import serializers

from apps.academics.models import Class, Section
from apps.user_account.models import UserAccount
from apps.user_profile.models import UserProfile
from apps.user_profile.serializers import AccountProfileOnboardSerializer

from .constants import BLOOD_GROUP_MAX_LENGTH, STUDENT_REQUIRED_ROLE
from .models import (
    Student, StudentDocument, StudentAttendance,
    Exam, ExamResult, StudentPromotion,
)


class StudentSerializer(serializers.ModelSerializer):
    """Student school record.

    Personal details (name, address, date of birth) belong to
    ``user_profile.UserProfile``; ``full_name`` / ``username`` are exposed here
    for convenience so list screens need no extra round trip.

    Like the teacher record, the API accepts a write-only ``user`` (UserAccount
    PK) alias that resolves -- creating if needed -- the account's
    ``UserProfile`` in the request's school, so the admin UI never has to know
    which UserProfile row belongs to a given account.
    """
    full_name = serializers.CharField(source='user_profile', read_only=True)
    username = serializers.CharField(
        source='user_profile.user_account.username', read_only=True
    )
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    # Write-only: the account the student record belongs to.
    user = serializers.IntegerField(write_only=True)
    # The profile may be supplied directly (UserProfile PK) or resolved from
    # ``user``; it is not required on its own.
    user_profile = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), required=False
    )

    class Meta:
        model = Student
        fields = [
            'id', 'tenant', 'user_profile', 'user', 'full_name', 'username',
            'school_class', 'class_name', 'section', 'section_name',
            'roll_number', 'admission_date', 'blood_group',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_user(self, value):
        if not UserAccount.objects.filter(pk=value).exists():
            raise serializers.ValidationError('User account not found.')
        return value

    @staticmethod
    def _profile_for_account(account_id):
        """Return (creating if needed) the UserProfile for a UserAccount PK."""
        account = UserAccount.objects.get(pk=account_id)
        profile, _ = UserProfile.objects.get_or_create(
            user_account=account,
            defaults={'first_name': account.username or ''},
        )
        return profile

    def create(self, validated_data):
        account_id = validated_data.pop('user', None)
        if account_id is not None:
            validated_data['user_profile'] = self._profile_for_account(account_id)
        elif validated_data.get('user_profile') is None:
            raise serializers.ValidationError(
                'Either "user_profile" or "user" is required to create a student.'
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        account_id = validated_data.pop('user', None)
        if account_id is not None:
            validated_data['user_profile'] = self._profile_for_account(account_id)
        return super().update(instance, validated_data)


class StudentOnboardSerializer(AccountProfileOnboardSerializer):
    """Create a student together with the account and profile it needs.

    The account fields and every personal-detail field of ``UserProfile``
    (phone, gender, date of birth, nationality, address, photo) come from
    ``AccountProfileOnboardSerializer``, which writes ``UserAccount``,
    ``UserProfile`` and ``TenantMembership`` in one transaction. This subclass
    adds the school record:

    * the membership role is always ``STUDENT_REQUIRED_ROLE`` -- the role
      ``Student.clean()`` requires in the school and one every creator that
      may write admissions (admin, HOD, super admin) is allowed to grant;
    * ``school_class`` / ``section`` must belong to the school being
      provisioned and must match each other;
    * the school's ``max_students`` plan limit is checked by the view before
      anything is written.

    Instantiate with ``context={'request': ..., 'tenant': <school>}``.
    """

    RECORD_MODEL = Student
    RECORD_SERIALIZER_CLASS = StudentSerializer

    # --- School record (``students.Student``) ---
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=Class.objects.all(), required=False, allow_null=True, default=None
    )
    section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(), required=False, allow_null=True, default=None
    )
    roll_number = serializers.IntegerField(required=False, allow_null=True, default=None)
    admission_date = serializers.DateField(required=False, allow_null=True, default=None)
    blood_group = serializers.CharField(
        max_length=BLOOD_GROUP_MAX_LENGTH, required=False, allow_blank=True, default=''
    )

    def validate_school_class(self, value):
        if value is not None and value.tenant_id != self.require_tenant().pk:
            raise serializers.ValidationError('This class belongs to another school.')
        return value

    def validate_section(self, value):
        if value is not None and value.tenant_id != self.require_tenant().pk:
            raise serializers.ValidationError('This section belongs to another school.')
        return value

    def validate(self, attrs):
        school_class = attrs.get('school_class')
        section = attrs.get('section')
        if (
            section is not None
            and school_class is not None
            and section.school_class_id != school_class.pk
        ):
            raise serializers.ValidationError(
                {'section': 'Section must belong to the selected class.'}
            )
        return super().validate(attrs)

    def resolve_membership_role(self, attrs):
        return STUDENT_REQUIRED_ROLE


class StudentDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(
        source='get_document_type_display', read_only=True
    )

    class Meta:
        model = StudentDocument
        fields = [
            'id', 'tenant', 'student', 'document_type',
            'document_type_display', 'title', 'file',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source='student.user_profile', read_only=True
    )

    class Meta:
        model = StudentAttendance
        fields = [
            'id', 'tenant', 'student', 'student_name',
            'academic_year', 'section', 'date', 'status',
            'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class ExamSerializer(serializers.ModelSerializer):
    exam_type_display = serializers.CharField(
        source='get_exam_type_display', read_only=True
    )

    class Meta:
        model = Exam
        fields = [
            'id', 'tenant', 'name', 'exam_type', 'exam_type_display',
            'academic_year', 'start_date', 'end_date', 'description',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class ExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source='student.user_profile', read_only=True
    )
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    exam_name = serializers.CharField(source='exam.name', read_only=True)

    class Meta:
        model = ExamResult
        fields = [
            'id', 'tenant', 'exam', 'exam_name', 'student', 'student_name',
            'subject', 'subject_name', 'marks_obtained', 'max_marks',
            'grade', 'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class StudentPromotionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source='student.user_profile', read_only=True
    )
    from_class_name = serializers.CharField(source='from_class.name', read_only=True)
    to_class_name = serializers.CharField(source='to_class.name', read_only=True)

    class Meta:
        model = StudentPromotion
        fields = [
            'id', 'tenant', 'student', 'student_name',
            'from_class', 'from_class_name', 'to_class', 'to_class_name',
            'from_academic_year', 'to_academic_year',
            'promoted_by', 'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'promoted_by', 'created_at', 'updated_at']
