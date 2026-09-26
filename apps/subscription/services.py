"""Shared subscription operations.

Both the direct super-admin endpoints (``SubscriptionViewSet``) and the
approval of school requests (``SubscriptionRequestViewSet``) apply plan
changes through these helpers, so a term/plan movement always records exactly
one revenue event and the renewal/upgrade semantics stay identical everywhere.
"""
import datetime
from decimal import Decimal

from django.utils import timezone

from .models import PaymentStatus, Subscription, SubscriptionPayment


def renew_subscription(subscription: Subscription) -> Subscription:
    """Extend ``subscription`` by its plan's duration and record a renewal."""
    now = timezone.now()
    base = subscription.end_date if subscription.end_date > now else now
    subscription.end_date = base + datetime.timedelta(days=subscription.plan.duration_days)
    subscription.is_active = True
    subscription.save(update_fields=['end_date', 'is_active'])

    SubscriptionPayment.objects.create(
        subscription=subscription,
        plan=subscription.plan,
        amount=subscription.plan.price,
        status=PaymentStatus.PAID,
        is_renewal=True,
    )
    return subscription


def change_subscription_plan(subscription: Subscription, plan) -> Subscription:
    """Switch ``subscription`` to ``plan``, recalculate its period and bill."""
    subscription.plan = plan
    subscription.end_date = subscription.start_date + datetime.timedelta(
        days=plan.duration_days
    )
    subscription.is_active = True
    subscription.save(update_fields=['plan', 'end_date', 'is_active'])

    SubscriptionPayment.objects.create(
        subscription=subscription,
        plan=plan,
        amount=plan.price,
        status=PaymentStatus.PAID,
        is_renewal=True,
    )
    return subscription


def apply_subscription_request(request_obj) -> Subscription:
    """Fulfil an approved request against the tenant's live subscription.

    Renew keeps the current plan; change-plan moves to ``request_obj.plan``.
    Raises ``ValueError`` when the request cannot be fulfilled.
    """
    tenant = request_obj.tenant
    try:
        subscription = Subscription.objects.get(tenant=tenant)
    except Subscription.DoesNotExist:
        raise ValueError("This school has no subscription yet.")

    if request_obj.request_type == "renew":
        return renew_subscription(subscription)
    if request_obj.request_type == "change_plan":
        if request_obj.plan is None:
            raise ValueError("A change-plan request requires a target plan.")
        return change_subscription_plan(subscription, request_obj.plan)
    raise ValueError("Unknown request type.")