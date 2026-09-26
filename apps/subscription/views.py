import datetime
# subscription/views.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, ProtectedError, Q, Sum
from django.db.models.functions import TruncMonth
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.tenants.models import Tenant
from .models import PaymentStatus, Plan, Subscription, SubscriptionPayment, SubscriptionRequest
from .services import (
    apply_subscription_request,
    change_subscription_plan,
    renew_subscription,
)
from .serializers import (
    PlanSerializer, SubscriptionSerializer, SubscriptionPaymentSerializer,
    SubscriptionRequestSerializer,
)
from utils.permissions import (
    IsAdminOrSuperAdmin, IsSuperAdmin, get_active_membership, is_super_admin,
)
from apps.core.mixins import TenantAPIView, TenantViewSet
from .constants import SubscriptionRequestStatus


# -------------------------------
# 🧾 PLAN MANAGEMENT (SuperAdmin)
# -------------------------------
class PlanViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin can create, update, or delete subscription plans.
    All authenticated users can view plans.
    """
    queryset = Plan.objects.all().order_by("price", "name")
    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This plan cannot be deleted because it is assigned to one or more schools."},
                status=status.HTTP_400_BAD_REQUEST,
            )


# -------------------------------
# 🏢 SUBSCRIPTION MANAGEMENT
# -------------------------------
class SubscriptionRequestViewSet(TenantViewSet):
    """
    Renew / change-plan requests submitted by schools.

    - Tenant admins: submit a request for their school, list their own
      requests, and cancel one that is still pending.
    - Super admin (platform): sees every school's requests and approves or
      rejects them. Approving applies the change through ``services``, exactly
      like the direct admin endpoints, so the payment history stays consistent.
    """
    serializer_class = SubscriptionRequestSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [IsSuperAdmin()]
        return [IsAdminOrSuperAdmin()]

    def get_queryset(self):
        qs = SubscriptionRequest.objects.select_related(
            "tenant", "plan", "requested_by", "processed_by"
        ).all()
        tenant = getattr(self.request, "tenant", None)

        if tenant is not None:
            return qs.filter(tenant=tenant)
        if is_super_admin(self.request.user):
            return qs
        membership = get_active_membership(self.request.user)
        if membership is not None:
            return qs.filter(tenant=membership.tenant)
        return qs.none()

    def perform_create(self, serializer):
        tenant = self.require_tenant()

        if SubscriptionRequest.objects.filter(
            tenant=tenant, status=SubscriptionRequestStatus.PENDING
        ).exists():
            raise ValidationError({
                "message": (
                    "This school already has a pending request. "
                    "Cancel it before submitting a new one."
                )
            })

        request_type = serializer.validated_data["request_type"]
        plan = serializer.validated_data.get("plan")

        if request_type == "change_plan":
            subscription = Subscription.objects.filter(tenant=tenant).first()
            if subscription is not None and subscription.plan_id == plan.id:
                raise ValidationError({
                    "plan": "This is already the school's current plan."
                })

        serializer.save(
            tenant=tenant,
            requested_by=self.request.user,
            status=SubscriptionRequestStatus.PENDING,
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """A school withdraws its own pending request."""
        obj = self.get_object()
        if obj.status != SubscriptionRequestStatus.PENDING:
            raise ValidationError({
                "message": "Only pending requests can be cancelled."
            })
        tenant = getattr(request, "tenant", None)
        if tenant is not None and obj.tenant_id != tenant.tenant_id:
            raise ValidationError({
                "message": "You can only cancel your own school's request."
            })
        obj.status = SubscriptionRequestStatus.CANCELLED
        obj.save(update_fields=["status"])
        return Response(self.get_serializer(obj).data)

    def _resolve_notes(self, request):
        notes = request.data.get("notes") if isinstance(request.data, dict) else None
        return (notes or "").strip()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a pending request and apply it to the school's subscription."""
        obj = self.get_object()
        if obj.status != SubscriptionRequestStatus.PENDING:
            raise ValidationError({
                "message": "Only pending requests can be approved."
            })
        with transaction.atomic():
            try:
                apply_subscription_request(obj)
            except ValueError as exc:
                raise ValidationError({"message": str(exc)})
            obj.status = SubscriptionRequestStatus.APPROVED
            obj.processed_by = request.user
            obj.responded_at = timezone.now()
            obj.admin_notes = self._resolve_notes(request)
            obj.save(update_fields=[
                "status", "processed_by", "responded_at", "admin_notes",
            ])
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a pending request without touching the subscription."""
        obj = self.get_object()
        if obj.status != SubscriptionRequestStatus.PENDING:
            raise ValidationError({
                "message": "Only pending requests can be rejected."
            })
        obj.status = SubscriptionRequestStatus.REJECTED
        obj.processed_by = request.user
        obj.responded_at = timezone.now()
        obj.admin_notes = self._resolve_notes(request)
        obj.save(update_fields=[
            "status", "processed_by", "responded_at", "admin_notes",
        ])
        return Response(self.get_serializer(obj).data)


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

    def get_queryset(self):
        # ``self.queryset`` is a single, class-level QuerySet instance. Iterating it
        # populates its result cache, and DRF's ``filter_queryset()`` returns that
        # very object unchanged when no filter backends are configured. Every later
        # request that takes the unscoped branch (super admins) would then replay
        # the rows cached by the first request - e.g. a deleted school's
        # subscription kept showing up in the platform list. ``.all()`` returns a
        # clone with no result cache, forcing a fresh query per request (this is
        # what ``GenericAPIView.get_queryset()`` does for ``self.queryset``).
        qs = self.queryset.all()
        tenant = getattr(self.request, 'tenant', None)

        if tenant is not None:
            return qs.filter(tenant=tenant)
        if is_super_admin(self.request.user):
            return qs
        return qs.none()

    def perform_create(self, serializer):
        """
        Automatically sets subscription period based on plan duration.
        """
        plan = serializer.validated_data["plan"]
        tenant = self.require_tenant()

        if Subscription.objects.filter(tenant=tenant).exists():
            raise ValidationError({
                "tenant": "This school already has a subscription. Update it instead."
            })

        start_date = timezone.now()
        end_date = start_date + datetime.timedelta(days=plan.duration_days)

        instance = serializer.save(
            tenant=tenant,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )

        # First payment on this subscription = the initial order.
        SubscriptionPayment.objects.create(
            subscription=instance,
            plan=plan,
            amount=plan.price,
            status=PaymentStatus.PAID,
            payment_date=start_date,
        )

    def perform_update(self, serializer):
        """
        Auto-recalculate subscription end date on plan change,
        recording a renewal payment whenever the plan actually moves.
        """
        instance = serializer.instance
        was_plan_change = (
            "plan" in serializer.validated_data
            and instance.plan_id != serializer.validated_data["plan"].id
        )
        instance = serializer.save()

        if was_plan_change:
            change_subscription_plan(
                instance, serializer.validated_data["plan"]
            )

    @action(detail=True, methods=['post'], url_path='renew')
    def renew(self, request, pk=None):
        """Renew/extend a subscription and record the renewal payment."""
        subscription = self.get_object()
        renew_subscription(subscription)
        return Response(SubscriptionSerializer(subscription).data)


# -------------------------------
# 💼 CURRENT TENANT'S PLAN (Sidebar gating)
# -------------------------------
class MyPlanView(TenantAPIView):
    """The active school's subscription / feature entitlements.

    Any authenticated tenant member may read what the school's plan grants
    (feature keys, student cap, remaining days) so the UI can lock navigation
    items the plan does not include - and offer an upgrade instead.
    Super admins (no tenant context) get an empty entitlement payload.
    """

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        empty = {
            "plan": None,
            "plan_name": None,
            "plan_price": None,
            "plan_features": [],
            "is_active": False,
            "days_remaining": 0,
            "max_students": 0,
        }
        if tenant is None:
            return Response(empty)

        subscription = (
            Subscription.objects.filter(tenant=tenant, is_active=True)
            .select_related("plan")
            .first()
        )
        if subscription is None:
            return Response(empty)

        plan = subscription.plan
        return Response({
            "plan": plan.id,
            "plan_name": plan.name,
            "plan_price": str(plan.price),
            "plan_features": sorted(plan.feature_keys()),
            "is_active": subscription.days_remaining > 0,
            "days_remaining": subscription.days_remaining,
            "max_students": plan.max_students,
        })


# -------------------------------
# 💳 SUBSCRIPTION PAYMENTS (Orders)
# -------------------------------
class SubscriptionPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Orders/payments: super admin sees the whole platform, tenant admins
    only their own school's payments."""
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = SubscriptionPayment.objects.select_related(
            'subscription__tenant', 'plan'
        ).all()
        tenant = getattr(self.request, 'tenant', None)
        user = self.request.user
        if tenant is None and not is_super_admin(user):
            membership = get_active_membership(user)
            tenant = membership.tenant if membership else None
        if tenant is not None:
            return qs.filter(subscription__tenant=tenant)
        if is_super_admin(user):
            return qs
        return qs.none()


def _months_back(now, n):
    """Datetime at the start of the month ``n`` months before ``now``."""
    month_index = now.year * 12 + (now.month - 1) - n
    return datetime.datetime(
        month_index // 12, month_index % 12 + 1, 1, tzinfo=now.tzinfo
    )


# -------------------------------
# 📈 PLATFORM REVENUE ANALYTICS (SuperAdmin)
# -------------------------------
class RevenueAnalyticsView(APIView):
    """Platform-wide revenue analytics for the super admin dashboard.

    Chains the platform funnel Schools -> Subscriptions -> Plans -> Payments
    -> Revenue, plus revenue broken down by plan and by month (last 12).
    Only ``status='paid'`` payments count as revenue. Super admins are
    platform-level and unbound to any tenant, so this must NOT use the
    tenant-bound ``TenantAPIView``.
    """
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = datetime.datetime(now.year, 1, 1, tzinfo=now.tzinfo)

        paid = SubscriptionPayment.objects.filter(status=PaymentStatus.PAID)
        total_revenue = paid.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        monthly_revenue = (
            paid.filter(payment_date__gte=month_start).aggregate(s=Sum('amount'))['s']
            or Decimal('0')
        )
        yearly_revenue = (
            paid.filter(payment_date__gte=year_start).aggregate(s=Sum('amount'))['s']
            or Decimal('0')
        )

        subs = Subscription.objects.all()
        active_subscriptions = subs.filter(is_active=True, end_date__gte=now).count()
        cancelled_or_expired = subs.filter(
            Q(is_active=False) | Q(end_date__lt=now)
        ).count()

        new_payments = paid.filter(is_renewal=False)
        new_subscriptions = new_payments.count()
        new_subscriptions_this_month = (
            new_payments.filter(payment_date__gte=month_start).count()
        )
        renewals = paid.filter(is_renewal=True).count()

        revenue_by_plan = [
            {
                'plan': row['plan__name'],
                'revenue': row['revenue'],
                'payments': row['payments'],
            }
            for row in paid.values('plan__name').annotate(
                revenue=Sum('amount'), payments=Count('id')
            ).order_by('-revenue')
        ]

        # Revenue by month for the last 12 months, zero-filled for gaps.
        twelve_months_ago = _months_back(now, 11)
        month_rows = (
            paid.filter(payment_date__gte=twelve_months_ago)
            .annotate(month=TruncMonth('payment_date'))
            .values('month')
            .annotate(revenue=Sum('amount'), payments=Count('id'))
        )
        by_label = {row['month'].strftime('%Y-%m'): row for row in month_rows}
        revenue_by_month = []
        for i in range(12):
            month = _months_back(now, 11 - i)
            row = by_label.get(month.strftime('%Y-%m'))
            revenue_by_month.append({
                'month': month.strftime('%Y-%m'),
                'revenue': row['revenue'] if row else Decimal('0'),
                'payments': row['payments'] if row else 0,
            })

        recent_payments = SubscriptionPaymentSerializer(
            SubscriptionPayment.objects.select_related('subscription__tenant', 'plan')
            .filter(status=PaymentStatus.PAID)
            .order_by('-payment_date')[:8],
            many=True,
        ).data

        return Response({
            'total_revenue': total_revenue,
            'monthly_revenue': monthly_revenue,
            'yearly_revenue': yearly_revenue,
            'active_subscriptions': active_subscriptions,
            'new_subscriptions': new_subscriptions,
            'new_subscriptions_this_month': new_subscriptions_this_month,
            'renewals': renewals,
            'cancelled_or_expired': cancelled_or_expired,
            'school_count': Tenant.objects.count(),
            'subscription_count': subs.count(),
            'plan_count': Plan.objects.count(),
            'payment_count': paid.count(),
            'revenue_by_plan': revenue_by_plan,
            'revenue_by_month': revenue_by_month,
            'recent_payments': recent_payments,
        })


# -------------------------------
# ✅ PUBLIC READ-ONLY ACTIVE PLAN LIST
# -------------------------------
class ActivePlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for listing all available (active) plans.
    """
    queryset = Plan.objects.filter(is_active=True).order_by("price", "name")
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated]
