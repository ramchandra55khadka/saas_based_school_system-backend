from rest_framework import generics, viewsets, status, permissions
from rest_framework.response import Response
from django.utils import timezone
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer
from accounts.permissions import IsSuperAdmin, IsAdminOnly, IsAdminOrSuperAdmin


# -------------------------------
# 🧾 PLAN MANAGEMENT (SuperAdmin)
# -------------------------------
class PlanViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin can create, update, or delete subscription plans.
    All users can view plans.
    """
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]  # Only SuperAdmin can modify plans # we take from accounts.permissions
        return [permissions.IsAuthenticated()]


# -------------------------------
# 🏢 SUBSCRIPTION MANAGEMENT
# -------------------------------
class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin can assign or modify organization subscriptions.
    Admins can only view their organization’s subscription.
    """
    queryset = Subscription.objects.select_related("organization", "plan").all()  #always inclue all() . if not include it will retirve only one
    serializer_class = SubscriptionSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return [IsAdminOrSuperAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == "super-admin":
            return self.queryset
        return self.queryset.filter(organization=user.organization)

    def perform_create(self, serializer):
        plan = serializer.validated_data["plan"]
        org = serializer.validated_data["organization"]
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(days=plan.duration_days)
        serializer.save(
            organization=org,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )

