from rest_framework import serializers

from apps.user_profile.serializers import AccountProfileOnboardSerializer

from .constants import PARENT_REQUIRED_ROLE
from .models import Parent, StudentGuardian


class ParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = '__all__'
        read_only_fields = ['tenant']


class StudentGuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGuardian
        fields = '__all__'
        read_only_fields = ['tenant']


class ParentOnboardSerializer(AccountProfileOnboardSerializer):
    """Create a parent together with the account and profile it needs.

    The account fields and every personal-detail field of ``UserProfile`` come
    from ``AccountProfileOnboardSerializer``, which writes ``UserAccount``,
    ``UserProfile`` and ``TenantMembership`` in one transaction. This subclass
    adds the school record (``parents.Parent``), the membership role always
    being ``PARENT_REQUIRED_ROLE``.

    Instantiate with ``context={'request': ..., 'tenant': <school>}``.
    """

    RECORD_MODEL = Parent
    RECORD_SERIALIZER_CLASS = ParentSerializer

    # --- School record (``parents.Parent``) ---
    occupation = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    emergency_contact = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=''
    )

    def resolve_membership_role(self, attrs):
        return PARENT_REQUIRED_ROLE