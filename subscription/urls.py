# subscription/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SubscriptionViewSet, ActivePlanViewSet

router = DefaultRouter()

#  SuperAdmin: Manage plans
router.register(r'plans', PlanViewSet, basename='plan')

#  Tenant + SuperAdmin: Manage subscriptions
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

#  Public read-only: List all active plans
router.register(r'active-plans', ActivePlanViewSet, basename='active-plan')

urlpatterns = [
    path('', include(router.urls)),
]
