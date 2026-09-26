from rest_framework import serializers

from apps.tenants.models import Department
from apps.user_account.constants import RoleChoices
from apps.user_profile.serializers import AccountProfileOnboardSerializer

from .constants import (
    DESIGNATION_ALLOWED_ROLES,
    DESIGNATION_CHOICES,
    DESIGNATION_DEFAULT,
    DESIGNATION_DEFAULT_ROLE,
    EMPLOYEE_ID_MAX_LENGTH,
    QUALIFICATION_CHOICES,
)
from .models import Staff


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = '__all__'
        read_only_fields = ['tenant']



class StaffOnboardSerializer(AccountProfileOnboardSerializer):
    """Create a staff member together with the account and profile it needs.

    The account fields and every personal-detail field of ``UserProfile``
    (phone, gender, date of birth, nationality, address, photo) come from
    ``AccountProfileOnboardSerializer``, which writes ``UserAccount``,
    ``UserProfile`` and ``TenantMembership`` in one transaction. This subclass
    adds the employment fields and the staff-specific rules:

    * the membership role defaults to ``DESIGNATION_DEFAULT_ROLE[designation]``
      or may be passed explicitly, as long as ``Staff.clean()`` would accept it
      (``DESIGNATION_ALLOWED_ROLES[designation]``);
    * the creator must be allowed to grant that role -- ``grantable_roles``,
      the same escalation matrix the user-management API enforces;
    * the ``department`` must belong to the school being provisioned.

    A failure anywhere (duplicate username, employee ID already taken,
    mismatched role, ...) leaves nothing behind.

    Instantiate with ``context={'request': ..., 'tenant': <school>}``.
    """

    RECORD_MODEL = Staff
    RECORD_SERIALIZER_CLASS = StaffSerializer

    # --- Employment (``staff.Staff``) ---
    designation = serializers.ChoiceField(choices=DESIGNATION_CHOICES)
    # Optional: derived from the designation when omitted.
    role = serializers.ChoiceField(
        choices=RoleChoices.choices, required=False, allow_blank=True
    )
    employee_id = serializers.CharField(
        max_length=EMPLOYEE_ID_MAX_LENGTH, required=False, allow_blank=True, default=''
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True, default=None
    )
    qualification = serializers.ChoiceField(
        choices=QUALIFICATION_CHOICES, required=False, allow_blank=True, default=''
    )
    specialization = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=''
    )
    date_of_joining = serializers.DateField(required=False, allow_null=True, default=None)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_department(self, value):
        if value is not None and value.tenant_id != self.require_tenant().pk:
            raise serializers.ValidationError('This department belongs to another school.')
        return value

    def resolve_membership_role(self, attrs):
        """The designation's default role, or an explicit one that fits it."""
        designation = attrs.get('designation', DESIGNATION_DEFAULT)
        role = attrs.get('role') or DESIGNATION_DEFAULT_ROLE[designation]
        if role not in DESIGNATION_ALLOWED_ROLES[designation]:
            raise serializers.ValidationError({
                'role': (
                    f'Role "{role}" cannot hold the "{designation}" designation in '
                    'this school.'
                )
            })
        return role
