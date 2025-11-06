# subscription/views.py
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework import viewsets
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer
from core.permissions import IsSuperAdmin, IsAdminOrSuperAdmin
from core.mixins import TenantViewSet


# -------------------------------
# 🧾 PLAN MANAGEMENT (SuperAdmin)
# -------------------------------
class PlanViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin can create, update, or delete subscription plans.
    All authenticated users can view plans.
    """
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return [permissions.IsAuthenticated()]


# -------------------------------
# 🏢 SUBSCRIPTION MANAGEMENT
# -------------------------------
class SubscriptionViewSet(TenantViewSet):
    """
    Handles tenant-specific subscriptions.
    - SuperAdmin: full access
    - Tenant admin: limited to their tenant
    """
    queryset = Subscription.objects.select_related("tenant", "plan").all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def perform_create(self, serializer):
        """
        Automatically sets subscription period based on plan duration.
        """
        plan = serializer.validated_data["plan"]
        tenant = serializer.validated_data.get("tenant", self.get_tenant())

        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(days=plan.duration_days)

        serializer.save(
            tenant=tenant,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )

    def perform_update(self, serializer):
        """
        Auto-recalculate subscription end date on plan change or renewal.
        """
        instance = serializer.instance
        plan = serializer.validated_data.get("plan", instance.plan)

        if "plan" in serializer.validated_data:
            instance.end_date = instance.start_date + timezone.timedelta(days=plan.duration_days)

        serializer.save()


# -------------------------------
# ✅ PUBLIC READ-ONLY ACTIVE PLAN LIST
# -------------------------------
class ActivePlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for listing all available (active) plans.
    """
    queryset = Plan.objects.all().order_by("price")
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated]
