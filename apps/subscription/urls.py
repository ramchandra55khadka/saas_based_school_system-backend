# subscription/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PlanViewSet, SubscriptionViewSet, ActivePlanViewSet,
    SubscriptionPaymentViewSet, RevenueAnalyticsView,
    SubscriptionRequestViewSet, MyPlanView,
)

router = DefaultRouter()

#  SuperAdmin: Manage plans
router.register(r'plans', PlanViewSet, basename='plan')

#  Tenant + SuperAdmin: Manage subscriptions
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

#  Renew / change-plan requests schools submit for their subscription
router.register(r'requests', SubscriptionRequestViewSet, basename='subscription-request')

#  Payments / orders behind every subscription (revenue events)
router.register(r'payments', SubscriptionPaymentViewSet, basename='subscription-payment')

#  Public read-only: List all active plans
router.register(r'active-plans', ActivePlanViewSet, basename='active-plan')

urlpatterns = [
    path('', include(router.urls)),
    # Sidebar gating: any tenant member reads their school's plan entitlements
    path('my-plan/', MyPlanView.as_view(), name='my-plan'),
    # Super-admin platform-wide revenue analytics
    path('revenue-analytics/', RevenueAnalyticsView.as_view(), name='revenue-analytics'),
]
