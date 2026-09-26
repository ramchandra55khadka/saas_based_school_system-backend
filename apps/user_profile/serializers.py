"""Personal profiles, plus the shared "onboard a person" serializer base.

Every screen that creates a person in one dialog (staff, students, ...) has to
write the same three rows first -- ``UserAccount``, ``UserProfile`` and a
``TenantMembership`` -- before the role-specific record (``Staff``,
``Student``, ...). ``AccountProfileOnboardSerializer`` owns exactly that: the
account fields, the profile fields and the atomic creation of those three rows.
The subclass only supplies the role-specific input fields and decides which
membership role to grant, so all onboarding endpoints keep every
``UserProfile`` column accepted -- see ``PROFILE_ONBOARD_FIELDS`` and
``apps/user_profile/tests.py``.
"""
from django.db import transaction
from rest_framework import serializers

from apps.core.mixins import validate_instance
from apps.user_account.models import TenantMembership, UserAccount
from utils.permissions import grantable_roles

from .constants import GENDER_CHOICES, NATIONALITY_MAX_LENGTH
from .models import UserProfile

# The ``UserProfile`` columns an onboarding payload fills. ``uuid`` is
# generated and ``user_account`` / the timestamps are bookkeeping, so every
# other column must appear here -- a test asserts the tuple stays equal to the
# model's fields, which is what stops a profile column from being forgotten.
PROFILE_ONBOARD_FIELDS = (
    'first_name', 'last_name', 'phone', 'gender',
    'date_of_birth', 'nationality', 'address', 'profile_image',
)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class AccountProfileOnboardSerializer(serializers.Serializer):
    """Flat payload that provisions an account, its profile and its membership.

    This class owns the ``UserAccount`` fields (``email``, ``password``)
    and every personal-detail column of ``UserProfile``
    (``PROFILE_ONBOARD_FIELDS``). ``save()`` writes account, profile and
    membership atomically, then hands what is left -- the role-specific
    fields -- to ``create_role_record``; the response is rendered by
    ``RECORD_SERIALIZER_CLASS``.

    The membership role comes from ``resolve_membership_role(attrs)`` and must
    be grantable by the caller (``grantable_roles`` -- the same escalation
    matrix the user-management API enforces). A failure anywhere (duplicate
    email, taken employee ID / roll number, ...) leaves nothing behind.

    Instantiate with ``context={'request': ..., 'tenant': <school>}``.
    """

    #: ``UserProfile`` columns filled from this payload (see module note).
    PROFILE_FIELDS = PROFILE_ONBOARD_FIELDS
    #: Role-specific model to create (e.g. ``staff.Staff``); set by subclasses.
    RECORD_MODEL = None
    #: Serializer that renders the created record back to the client.
    RECORD_SERIALIZER_CLASS = None

    # --- User account (``user_account.UserAccount``) ---
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    # --- Personal details (``user_profile.UserProfile``) ---
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    gender = serializers.ChoiceField(
        choices=GENDER_CHOICES, required=False, allow_blank=True, default=''
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    nationality = serializers.CharField(
        max_length=NATIONALITY_MAX_LENGTH, required=False, allow_blank=True, default=''
    )
    address = serializers.CharField(required=False, allow_blank=True, default='')
    # Photo: a file on multipart requests, ``null``/absent on JSON.
    profile_image = serializers.ImageField(required=False, allow_null=True, default=None)

    # --- Hooks the role-specific serializers implement/override ---

    def resolve_membership_role(self, attrs):
        """Return the ``TenantMembership`` role to grant for this payload."""
        raise NotImplementedError(
            f'{type(self).__name__} must implement resolve_membership_role().'
        )

    def create_role_record(self, tenant, profile, validated_data):
        """Create the role-specific record from the remaining payload.

        The default builds ``RECORD_MODEL`` for the school and the profile and
        runs ``full_clean()`` first, so model-level rules (designation/role
        match, class tenancy, unique roll number, ...) surface as a clean 400
        instead of a database error.
        """
        record = self.RECORD_MODEL(tenant=tenant, user_profile=profile, **validated_data)
        validate_instance(record)
        record.save()
        return record

    def validate_email(self, value):
        tenant = self.require_tenant()
        if UserAccount.objects.filter(
            memberships__tenant=tenant,
            email__iexact=value,
        ).exists():
            raise serializers.ValidationError('This email is already registered in this school.')
        return value

    def validate(self, attrs):
        role = self.resolve_membership_role(attrs)
        request = self.context.get('request')
        if role not in grantable_roles(getattr(request, 'user', None), self.require_tenant()):
            # Same wording as the user-management API, so the UI shows one message.
            raise serializers.ValidationError(
                f'You cannot create a user with role "{role}" in this school.'
            )
        attrs['role'] = role
        return attrs

    def require_tenant(self):
        """The school being provisioned (set by the view from its request)."""
        tenant = self.context.get('tenant')
        if tenant is None:
            raise serializers.ValidationError({'message': 'No active tenant for this request.'})
        return tenant

    @transaction.atomic
    def create(self, validated_data):
        tenant = self.require_tenant()
        role = validated_data.pop('role')

        email = validated_data.pop('email')
        account = UserAccount(
            email=email,
            username=UserAccount.generate_unique_username(email, tenant=tenant),
        )
        account.set_password(validated_data.pop('password'))
        account.save()

        profile = UserProfile.objects.create(
            user_account=account,
            **{name: validated_data.pop(name) for name in self.PROFILE_FIELDS},
        )

        TenantMembership.objects.create(
            user=account, tenant=tenant, role=role, is_active=True
        )

        # Whatever is left are the role-specific fields (Staff, Student, ...).
        return self.create_role_record(tenant, profile, validated_data)

    def to_representation(self, instance):
        """Return the created role record, not the flat onboarding payload."""
        return self.RECORD_SERIALIZER_CLASS(instance, context=self.context).data


