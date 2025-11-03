from rest_framework import serializers
from .models import Plan, Subscription
from accounts.models import Organization


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "plan", "description", "price", "duration_days", "max_users", "created_at"]
        read_only_fields = ["id", "created_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(), source="plan", write_only=True
    )
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), required=True
    )
    days_remaining = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "organization",
            "plan",
            "plan_id",
            "start_date",
            "end_date",
            "is_active",
            "auto_renew",
            "days_remaining",
        ]
        read_only_fields = ["id", "start_date", "end_date", "is_active", "days_remaining"]
