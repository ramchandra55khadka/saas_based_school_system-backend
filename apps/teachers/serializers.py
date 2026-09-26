from rest_framework import serializers

from apps.academics.models import Section, Subject
from apps.core.mixins import validate_instance
from apps.staff.constants import DESIGNATION_CHOICES, DESIGNATION_TEACHER
from apps.staff.models import Staff
from apps.staff.serializers import StaffOnboardSerializer
from apps.user_account.models import UserAccount
from apps.user_profile.models import UserProfile

from .constants import TEACHER_ONBOARD_FIELDS
from .models import Teacher, TeacherAttendance, LeaveRequest


class TeacherSerializer(serializers.ModelSerializer):
    """Teacher employment record.

    The model hangs off ``staff.Staff`` (which is OneToOne with
    ``user_profile.UserProfile``). The API keeps the old ``user`` (UserAccount
    PK) write alias so existing clients keep working: it resolves — creating
    if needed — the account's Staff record in the request's school.
    ``full_name`` / ``username`` / ``email`` are resolved through the profile,
    and ``employee_id`` / ``qualification`` / ``specialization`` /
    ``date_of_joining`` / ``is_active`` are write aliases for the shared Staff
    row. Date of birth lives on the profile and is not part of this resource.
    """
    full_name = serializers.CharField(source='staff.user_profile', read_only=True)
    username = serializers.CharField(
        source='staff.user_profile.user_account.username', read_only=True
    )
    email = serializers.EmailField(
        source='staff.user_profile.user_account.email', read_only=True
    )
    employee_id = serializers.CharField(
        source='staff.employee_id', required=False, allow_blank=True
    )
    qualification = serializers.CharField(
        source='staff.qualification', required=False, allow_blank=True
    )
    specialization = serializers.CharField(
        source='staff.specialization', required=False, allow_blank=True
    )
    date_of_joining = serializers.DateField(
        source='staff.date_of_joining', required=False, allow_null=True
    )
    is_active = serializers.BooleanField(source='staff.is_active', required=False)
    phone = serializers.CharField(
        source='staff.user_profile.phone', required=False, allow_blank=True
    )
    address = serializers.CharField(
        source='staff.user_profile.address', required=False, allow_blank=True
    )
    # Read alias so the list can show the subject without a second request.
    primary_subject_name = serializers.CharField(
        source='primary_subject.name', read_only=True
    )
    # Write-only: the account the teacher record belongs to.
    user = serializers.IntegerField(write_only=True, required=False)
    # Write-only: the shared staff row the teacher record hangs off. This is the
    # preferred way to create a teacher — the account and profile already exist
    # on the staff record, so nothing has to be re-created here.
    staff_id = serializers.PrimaryKeyRelatedField(
        queryset=Staff.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
        label='Staff member',
    )
    # Read alias so the list can hide staff that already have a teacher record.
    staff = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id', 'tenant', 'user', 'staff', 'staff_id', 'full_name',
            'username', 'email',
            'employee_id', 'qualification', 'specialization',
            'date_of_joining', 'is_active', 'phone', 'address',
            'teaching_license_number', 'primary_subject', 'primary_subject_name',
            'class_teacher_section', 'max_weekly_periods', 'office_hours', 'bio',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_user(self, value):
        if not UserAccount.objects.filter(pk=value).exists():
            raise serializers.ValidationError('User account not found.')
        return value

    def validate_staff_id(self, value):
        if value is not None:
            tenant = getattr(self.context.get('request'), 'tenant', None)
            if tenant is not None and value.tenant_id != tenant.pk:
                raise serializers.ValidationError(
                    'This staff member belongs to another school.'
                )
        return value

    def validate(self, attrs):
        # A teacher must hang off a staff row: either the staff picker
        # (``staff_id``) or the legacy account alias (``user``).
        if self.instance is None and not attrs.get('staff_id') and not attrs.get('user'):
            raise serializers.ValidationError(
                {'staff_id': 'Select a staff member.'}
            )
        return attrs

    @staticmethod
    def _profile_for_account(account_id):
        """Return (creating if needed) the profile for a UserAccount PK."""
        account = UserAccount.objects.get(pk=account_id)
        profile, _ = UserProfile.objects.get_or_create(
            user_account=account,
            defaults={'first_name': account.username or ''},
        )
        return profile

    def _staff_for_account(self, account_id):
        """Return (creating if needed) the Staff record of a UserAccount PK.

        The staff row is created in the request's school with
        ``designation='teacher'``; an existing staff record for the account is
        reused regardless of its type (the Teacher membership check on
        ``Teacher.clean()`` still gates the account's roles).
        """
        profile = self._profile_for_account(account_id)
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant is None:
            raise serializers.ValidationError(
                {'user': 'No active school for this request.'}
            )
        staff = Staff.objects.filter(user_profile=profile, tenant=tenant).first()
        if staff is None:
            staff = Staff.objects.create(
                tenant=tenant,
                user_profile=profile,
                designation=DESIGNATION_TEACHER,
            )
        return staff

    @staticmethod
    def _apply_related_details(staff, staff_data):
        """Persist write aliases that are stored on Staff/UserProfile."""
        if not staff_data:
            return

        profile_data = staff_data.pop('user_profile', {})
        staff_updates = []
        for field, value in staff_data.items():
            setattr(staff, field, value)
            staff_updates.append(field)
        if staff_updates:
            staff.save(update_fields=staff_updates)

        profile_updates = []
        for field, value in profile_data.items():
            setattr(staff.user_profile, field, value)
            profile_updates.append(field)
        if profile_updates:
            staff.user_profile.save(update_fields=profile_updates)

    def create(self, validated_data):
        account_id = validated_data.pop('user', None)
        staff_obj = validated_data.pop('staff_id', None)
        staff_data = validated_data.pop('staff', {})
        if staff_obj is not None:
            validated_data['staff'] = staff_obj
        elif account_id is not None:
            validated_data['staff'] = self._staff_for_account(account_id)
        teacher = super().create(validated_data)
        self._apply_related_details(teacher.staff, staff_data)
        return teacher

    def update(self, instance, validated_data):
        account_id = validated_data.pop('user', None)
        staff_obj = validated_data.pop('staff_id', None)
        staff_data = validated_data.pop('staff', {})
        if staff_obj is not None:
            validated_data['staff'] = staff_obj
        elif account_id is not None:
            validated_data['staff'] = self._staff_for_account(account_id)
        teacher = super().update(instance, validated_data)
        self._apply_related_details(teacher.staff, staff_data)
        return teacher


class TeacherOnboardSerializer(StaffOnboardSerializer):
    """Create a teacher together with the staff, account and profile it needs.

    The account fields, every personal-detail field of ``UserProfile`` and the
    employment fields come from ``StaffOnboardSerializer``, which writes
    ``UserAccount``, ``UserProfile``, ``TenantMembership`` and ``Staff`` in one
    transaction. This subclass:

    * pins ``designation`` to ``teacher``, so the membership role resolves to
      ``teacher`` (or an explicit role the teacher designation allows, still
      checked against ``grantable_roles``);
    * adds the teaching columns (``TEACHER_ONBOARD_FIELDS``) and builds the
      ``Teacher`` row right after the staff record, inside the same
      transaction, so "Add teacher" produces the whole chain at once;
    * keeps ``primary_subject`` / ``class_teacher_section`` inside the school.

    A failure anywhere (duplicate username, employee ID already taken,
    cross-tenancy subject, ...) leaves nothing behind.

    Instantiate with ``context={'request': ..., 'tenant': <school>}``.
    """

    # The base creates the ``Staff`` record (``Teacher`` hangs off it) ...
    RECORD_MODEL = Staff
    # ... and the response describes the teaching record the dialog created.
    RECORD_SERIALIZER_CLASS = TeacherSerializer

    # A teacher is always teaching staff. The field stays declared so the
    # payload shape matches the staff dialog, but the value is pinned in
    # ``validate()`` -- this endpoint cannot mint another designation.
    designation = serializers.ChoiceField(
        choices=DESIGNATION_CHOICES, required=False, default=DESIGNATION_TEACHER
    )

    # --- Teaching record (``teachers.Teacher``) ---
    teaching_license_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=''
    )
    primary_subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), required=False, allow_null=True, default=None
    )
    class_teacher_section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(), required=False, allow_null=True, default=None
    )
    max_weekly_periods = serializers.IntegerField(
        min_value=0, required=False, allow_null=True, default=None
    )
    office_hours = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=''
    )
    bio = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_primary_subject(self, value):
        if value is not None and value.tenant_id != self.require_tenant().pk:
            raise serializers.ValidationError('This subject belongs to another school.')
        return value

    def validate_class_teacher_section(self, value):
        if value is not None and value.tenant_id != self.require_tenant().pk:
            raise serializers.ValidationError('This section belongs to another school.')
        return value

    def validate(self, attrs):
        # Always a teaching staff record: the designation drives which
        # membership roles ``Staff.clean()`` accepts and which role is granted.
        attrs['designation'] = DESIGNATION_TEACHER
        return super().validate(attrs)

    def create_role_record(self, tenant, profile, validated_data):
        """Build the shared ``Staff`` row first, then the teaching record."""
        teaching_data = {
            name: validated_data.pop(name) for name in TEACHER_ONBOARD_FIELDS
        }
        staff = super().create_role_record(tenant, profile, validated_data)
        teacher = Teacher(tenant=tenant, staff=staff, **teaching_data)
        validate_instance(teacher)
        teacher.save()
        return teacher


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(
        source='teacher.staff.user_profile', read_only=True
    )

    class Meta:
        model = TeacherAttendance
        fields = [
            'id', 'tenant', 'teacher', 'teacher_name',
            'date', 'status', 'check_in_time', 'check_out_time',
            'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class LeaveRequestSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(
        source='teacher.staff.user_profile', read_only=True
    )
    leave_type_display = serializers.CharField(
        source='get_leave_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'tenant', 'teacher', 'teacher_name',
            'leave_type', 'leave_type_display',
            'start_date', 'end_date', 'reason',
            'status', 'status_display',
            'approved_by', 'approved_by_name', 'responded_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant', 'teacher', 'approved_by', 'responded_at',
            'created_at', 'updated_at',
        ]

    def get_approved_by_name(self, obj):
        if obj.approved_by is None:
            return ''
        profile = getattr(obj.approved_by, 'profile', None)
        if profile is None:
            return obj.approved_by.username
        return f'{profile.first_name} {profile.last_name}'.strip() or obj.approved_by.username
