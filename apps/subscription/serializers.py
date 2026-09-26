# subscription/serializers.py
from rest_framework import serializers
from .models import (
    Feature, Plan, Subscription, SubscriptionPayment, SubscriptionRequest,
)
from .constants import SubscriptionRequestType, SubscriptionRequestStatus


class PlanSerializer(serializers.ModelSerializer):
    """
    Public-facing plan details.
    Used by super-admin and tenants to view available plans.

    ``features`` is the set of modules the plan unlocks, as ``FeatureKey``
    strings (``["students", "finance", ...]``). It is writable so the super
    admin can grant a module — e.g. ``finance``, which gates the Fees page —
    from the Plans screen; unknown or deactivated keys are rejected.
    """
    features = serializers.SlugRelatedField(
        slug_field="key",
        many=True,
        required=False,
        queryset=Feature.objects.filter(is_active=True),
        help_text="Feature keys granted by this plan.",
    )

    class Meta:
        model = Plan
        fields = [
            "id", "name", "price", "duration_days",
            "max_students", "features",
            "is_active", "created_at",
        ]
        read_only_fields = ["created_at"]


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ["id", "key", "name", "description", "is_active", "created_at"]
        read_only_fields = ["created_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Tenant subscription with enriched, read-only context.
    """
    tenant_name = serializers.CharField(source="tenant.tenant_name", read_only=True)
    org_code = serializers.CharField(source="tenant.org_code", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    plan_price = serializers.DecimalField(
        source="plan.price", max_digits=10, decimal_places=2, read_only=True
    )
    plan_duration_days = serializers.IntegerField(source="plan.duration_days", read_only=True)
    plan_features = serializers.SlugRelatedField(
        source="plan.features", slug_field="key", many=True, read_only=True
    )
    plan_max_students = serializers.IntegerField(source="plan.max_students", read_only=True)
    days_remaining = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields = [
            "id", "tenant", "tenant_name", "org_code",
            "plan", "plan_name", "plan_price", "plan_duration_days",
            "plan_features", "plan_max_students",
            "start_date", "end_date", "is_active", "days_remaining",
        ]
        read_only_fields = ["start_date", "end_date", "tenant", "days_remaining"]

    def validate_plan(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This plan is no longer available.")
        return value


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    """A subscription order/payment with flat, read-only context."""
    tenant_id = serializers.UUIDField(source="subscription.tenant.tenant_id", read_only=True)
    tenant_name = serializers.CharField(source="subscription.tenant.tenant_name", read_only=True)
    org_code = serializers.CharField(source="subscription.tenant.org_code", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    plan_price = serializers.DecimalField(
        source="plan.price", max_digits=10, decimal_places=2, read_only=True
    )
    payment_type = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPayment
        fields = [
            "id", "subscription", "tenant_id", "tenant_name", "org_code",
            "plan", "plan_name", "plan_price", "amount", "status", "method",
            "reference", "payment_date", "is_renewal", "payment_type",
            "created_at",
        ]
        read_only_fields = fields

    def get_payment_type(self, obj):
        return "Renewal" if obj.is_renewal else "New subscription"


class SubscriptionRequestSerializer(serializers.ModelSerializer):
    """A school's renew / change-plan request with flat, read-only context."""
    tenant_id = serializers.UUIDField(source="tenant.tenant_id", read_only=True)
    tenant_name = serializers.CharField(source="tenant.tenant_name", read_only=True)
    org_code = serializers.CharField(source="tenant.org_code", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, allow_null=True)
    plan_price = serializers.DecimalField(
        source="plan.price", max_digits=10, decimal_places=2,
        read_only=True, allow_null=True,
    )
    request_type_display = serializers.CharField(
        source="get_request_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionRequest
        fields = [
            "id", "tenant", "tenant_id", "tenant_name", "org_code",
            "request_type", "request_type_display",
            "plan", "plan_name", "plan_price",
            "message", "status", "status_display",
            "requested_by", "requested_by_name",
            "processed_by", "processed_by_name",
            "responded_at", "admin_notes",
            "created_at",
        ]
        read_only_fields = [
            "id", "tenant", "status", "requested_by",
            "processed_by", "responded_at", "admin_notes", "created_at",
        ]

    def get_requested_by_name(self, obj):
        user = obj.requested_by
        if not user:
            return None
        profile = getattr(user, "userprofile", None)
        if profile is not None:
            parts = [profile.first_name or "", profile.last_name or ""]
            if any(parts):
                return " ".join(parts).strip()
        return user.username

    def get_processed_by_name(self, obj):
        user = obj.processed_by
        return user.username if user else None

    def validate(self, attrs):
        request_type = attrs.get("request_type")
        plan = attrs.get("plan")

        if request_type == SubscriptionRequestType.CHANGE_PLAN and plan is None:
            raise serializers.ValidationError(
                {"plan": "A target plan is required for a change-plan request."}
            )
        if request_type == SubscriptionRequestType.RENEW and plan is not None:
            raise serializers.ValidationError(
                {"plan": "Renew requests keep the current plan; do not pick one."}
            )
        if plan is not None and not plan.is_active:
            raise serializers.ValidationError(
                {"plan": "This plan is no longer available."}
            )
        return attrs