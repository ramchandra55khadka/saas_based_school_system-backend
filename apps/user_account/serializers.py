from django.db import transaction
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.tenants.models import Tenant
from .models import TenantMembership, RoleChoices

User = get_user_model()


def account_full_name(user):
    profile = getattr(user, 'profile', None)
    if profile is None:
        return ''
    return f'{profile.first_name} {profile.last_name}'.strip()


class UserSerializer(serializers.ModelSerializer):
    """User CRUD serializer.

    Names live on the linked ``user_profile.UserProfile`` row, not on the
    account — ``full_name`` is derived from it (empty → the frontend falls
    back to ``username``). The verification flags are system-managed.
    """
    full_name = serializers.SerializerMethodField()
    email_is_verified = serializers.BooleanField(read_only=True)
    phone_is_verified = serializers.BooleanField(read_only=True)
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=RoleChoices.choices, write_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'full_name',
            'email_is_verified', 'phone_is_verified',
            'role', 'date_joined', 'password', 'roles',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_full_name(self, obj):
        return account_full_name(obj)

    def get_roles(self, obj):
        """Active membership roles across tenants (used to spot school admins)."""
        return [m.role for m in obj.memberships.filter(is_active=True)]

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('role', None)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('role', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class TenantMembershipSerializer(serializers.ModelSerializer):
    """Serializer for user's tenant memberships."""
    tenant_name = serializers.CharField(source='tenant.tenant_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = TenantMembership
        fields = [
            'id', 'tenant', 'tenant_name', 'role',
            'role_display', 'is_active', 'joined_at',
        ]
        read_only_fields = ['id', 'joined_at']


class SignupSerializer(serializers.Serializer):
    """Super-admin creates a tenant + initial admin user."""
    tenant_name = serializers.CharField()
    org_code = serializers.CharField()
    address = serializers.CharField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True, default=None)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True, default=None)
    logo = serializers.FileField(required=False, allow_null=True, allow_empty_file=False)
    established_year = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=1
    )
    admin_username = serializers.CharField()
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True)

    def validate_tenant_name(self, value):
        if Tenant.objects.filter(tenant_name__iexact=value).exists():
            raise serializers.ValidationError("A school with this name already exists.")
        return value

    def validate_org_code(self, value):
        if Tenant.objects.filter(org_code__iexact=value).exists():
            raise serializers.ValidationError("This org code is already taken.")
        return value

    def validate_admin_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_admin_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        tenant = Tenant.objects.create(
            tenant_name=validated_data['tenant_name'],
            org_code=validated_data['org_code'],
            address=validated_data.get('address') or '',
            phone=validated_data.get('phone') or '',
            email=validated_data.get('email') or '',
            website=validated_data.get('website') or '',
            logo=validated_data.get('logo'),
            established_year=validated_data.get('established_year'),
        )
        admin_user = User.objects.create(
            username=validated_data['admin_username'],
            email=validated_data['admin_email'],
        )
        admin_user.set_password(validated_data['admin_password'])
        admin_user.save()

        TenantMembership.objects.create(
            user=admin_user,
            tenant=tenant,
            role=RoleChoices.ADMIN,
            is_active=True,
        )
        return {'tenant': tenant, 'admin_user': admin_user}

    def to_representation(self, instance):
        """Serialize the (tenant, admin_user) pair created by ``create()``.

        The default implementation would try ``getattr(instance, 'tenant_name')``
        on a plain dict and blow up with a 500 *after* the rows were committed.
        """
        tenant = instance['tenant']
        admin_user = instance['admin_user']
        return {
            'message': 'Tenant and admin user created successfully',
            'tenant': {
                'tenant_id': str(tenant.tenant_id),
                'tenant_name': tenant.tenant_name,
                'org_code': tenant.org_code,
                'address': tenant.address,
                'phone': tenant.phone,
                'email': tenant.email,
                'website': tenant.website,
                'logo': tenant.logo.url if tenant.logo else None,
                'established_year': tenant.established_year,
            },
            'admin_user': {
                'id': admin_user.id,
                'username': admin_user.username,
                'email': admin_user.email,
                'role': RoleChoices.ADMIN,
            },
        }


class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only serializer for current user profile."""
    full_name = serializers.SerializerMethodField()
    memberships = TenantMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'full_name',
            'email_is_verified', 'phone_is_verified',
            'is_superuser', 'date_joined', 'memberships',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return account_full_name(obj)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT login that authenticates with **email + password**.

    ``User.email`` is ``unique=True``, so the email is a safe lookup key.
    SimpleJWT's default flow authenticates with ``USERNAME_FIELD`` (username);
    we replace that field with ``email`` and do the lookup ourselves.
    """

    default_error_messages = {
        'no_active_account': 'No active account found with the given credentials.'
    }
    email = serializers.EmailField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Drop SimpleJWT's default ``username`` field — login is email-only.
        self.fields.pop('username', None)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = User.objects.filter(email__iexact=email).first()
        authenticated = None
        if user is not None:
            # ModelBackend verifies the password and rejects inactive users.
            authenticated = authenticate(username=user.username, password=password)

        if authenticated is None:
            # Run the default password hasher once so that a wrong password and
            # an unknown email take a comparable time (Django's recommended
            # timing-attack mitigation for login by a non-username field).
            User().set_password(password)
            raise AuthenticationFailed(
                self.default_error_messages['no_active_account'],
                code='no_active_account',
            )

        self.user = authenticated
        # ``CookieTokenObtainPairView.post()`` mints fresh tokens from
        # ``serializer.user`` itself, so no token payload is needed here.
        return {}
