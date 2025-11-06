# subscription/serializers.py
from rest_framework import serializers
from .models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    """
    Public-facing plan details.
    Used by super-admin and tenants to view available plans.
    """
    name = serializers.CharField(source="get_plan_display", read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id", "plan", "name", "description", "price",
            "duration_days", "max_users", "is_active"
        ]
        read_only_fields = ["plan", "name"]


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Tenant subscription with enriched, read-only context.
    """
    tenant_name = serializers.CharField(source="tenant.tenant_name", read_only=True)
    org_code = serializers.CharField(source="tenant.org_code", read_only=True)
    plan_name = serializers.CharField(source="plan.get_plan_display", read_only=True)
    price = serializers.DecimalField(
        source="plan.price", max_digits=10, decimal_places=2, read_only=True
    )
    days_remaining = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields = [
            "id", "tenant", "tenant_name", "org_code",
            "plan", "plan_name", "price",
            "start_date", "end_date", "is_active", "auto_renew",
            "days_remaining", "is_expired",
            "created_at", "updated_at"
        ]
        read_only_fields = [
            "tenant", "created_at", "updated_at",
            "days_remaining", "is_expired"
        ]

    def validate_plan(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This plan is no longer available.")
        return value