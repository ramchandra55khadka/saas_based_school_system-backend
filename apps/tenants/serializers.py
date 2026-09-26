from rest_framework import serializers
from .models import Department, Tenant, SchoolSettings


class TenantSerializer(serializers.ModelSerializer):
    """Full school profile serializer."""
    class Meta:
        model = Tenant
        fields = [
            'tenant_id', 'tenant_name', 'slug', 'org_code', 'address',
            'phone', 'email', 'website', 'logo',
            'established_year', 'is_active', 'created_at',
        ]
        read_only_fields = ['tenant_id', 'created_at']


class TenantDetailSerializer(serializers.ModelSerializer):
    """School profile with subscription info."""
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'tenant_id', 'tenant_name', 'slug', 'org_code', 'address',
            'phone', 'email', 'website', 'logo',
            'established_year', 'is_active', 'created_at',
            'subscription_status',
        ]
        read_only_fields = ['tenant_id', 'created_at']

    def get_subscription_status(self, obj):
        sub = getattr(obj, 'subscription', None)
        if sub:
            return {
                'plan': str(sub.plan),
                'is_active': sub.is_active,
                'days_remaining': sub.days_remaining,
            }
        return None


class SchoolSettingsSerializer(serializers.ModelSerializer):
    """School settings serializer."""
    class Meta:
        model = SchoolSettings
        fields = [
            'id', 'tenant', 'academic_year_format',
            'grading_system', 'attendance_type', 'timezone',
        ]
        read_only_fields = ['tenant']


class DepartmentSerializer(serializers.ModelSerializer):
    """Department of the active school (the staff form's department pick-list)."""

    class Meta:
        model = Department
        fields = ['id', 'name', 'level', 'description', 'is_active']
        read_only_fields = ['id']

    def validate_name(self, value):
        """Keep ``unique_together = ('tenant', 'name')`` a form error, not a 500.

        ``tenant`` is injected by the viewset (it is not a serializer field), so
        DRF cannot build a unique-together validator for it and the constraint
        would only fire at INSERT time — surfacing as an IntegrityError. The
        active school comes from the request context, which DRF always passes.
        """
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant is None:
            return value
        duplicates = Department.objects.filter(tenant=tenant, name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                'This department already exists in this school.'
            )
        return value
