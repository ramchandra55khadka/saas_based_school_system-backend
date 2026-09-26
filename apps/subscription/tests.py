from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.core.tests import BaseTenantAPITestCase
from apps.subscription.constants import FeatureKey, SubscriptionRequestStatus
from apps.subscription.entitlements import (
    get_active_subscription,
    get_student_limit,
    has_feature,
)
from apps.subscription.models import (
    Feature, PaymentStatus, Plan, Subscription, SubscriptionPayment,
    SubscriptionRequest,
)


class FreePlanMigrationTests(BaseTenantAPITestCase):
    """The demo/trial Free plan ships via a data migration.

    Price is 0, the student cap is deliberately tiny, and only a core
    academic feature subset is granted - no communication/finance/library.
    """

    def test_free_plan_exists_with_demo_shape(self):
        plan = Plan.objects.get(name="Free")
        self.assertEqual(plan.price, 0)
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.duration_days, 30)
        self.assertEqual(plan.max_students, 10)
        keys = plan.feature_keys()
        for granted in (FeatureKey.STUDENTS, FeatureKey.TEACHERS,
                        FeatureKey.ACADEMICS, FeatureKey.REPORTS):
            self.assertIn(granted, keys)
        for excluded in (FeatureKey.COMMUNICATION, FeatureKey.FINANCE, FeatureKey.LIBRARY):
            self.assertNotIn(excluded, keys)

    def test_free_plan_grants_trial_read_only_no_gating_features(self):
        plan = Plan.objects.get(name="Free")
        self._subscribe_tenant_a(plan)
        self.assertTrue(has_feature(self.tenant_a, FeatureKey.STUDENTS))
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.FINANCE))
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.LIBRARY))
        self.assertEqual(get_student_limit(self.tenant_a), 10)

    def _subscribe_tenant_a(self, plan):
        Subscription.objects.create(
            tenant=self.tenant_a, plan=plan,
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
        )


class SubscriptionPlanTests(BaseTenantAPITestCase):
    def _make_plan(self, name="Basic Plan", **kwargs):
        return Plan.objects.create(
            name=name,
            price=kwargs.get("price", 1499.00),
            duration_days=kwargs.get("duration_days", 365),
            max_students=kwargs.get("max_students", 100),
            is_active=True,
        )

    def test_super_admin_can_delete_unused_plan(self):
        self.login(*self.super_admin_creds)
        plan = self._make_plan()

        response = self.client.delete(reverse("plan-detail", args=[plan.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.content)
        self.assertFalse(Plan.objects.filter(id=plan.id).exists())

    def test_delete_referenced_plan_returns_clean_400(self):
        """Deleting a plan a subscription references must not 500 (regression)."""
        self.login(*self.super_admin_creds)
        plan = self._make_plan()
        Subscription.objects.create(
            tenant=self.tenant_a,
            plan=plan,
            end_date=timezone.now() + timedelta(days=365),
        )

        response = self.client.delete(reverse("plan-detail", args=[plan.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertTrue(Plan.objects.filter(id=plan.id).exists())


class EntitlementTests(BaseTenantAPITestCase):
    """Feature-based access: the active plan dictates what a school may use.

    Plan-name comparisons must never drive feature checks - entitlement comes
    from the Subscription -> Plan -> Features relationship instead.
    """

    def _feature(self, key):
        feature, _ = Feature.objects.get_or_create(key=key, defaults={"name": key.label})
        return feature

    def _plan(self, name, features=()):
        plan = Plan.objects.create(
            name=name, price=100, duration_days=30,
            max_students=200, is_active=True,
        )
        plan.features.set([self._feature(fk) for fk in features])
        return plan

    def _subscribe(self, tenant, plan, days=30):
        Subscription.objects.create(
            tenant=tenant, plan=plan,
            end_date=timezone.now() + timedelta(days=days),
            is_active=True,
        )

    def test_granted_feature_is_true_granted_others_not(self):
        plan = self._plan("Premium", features=(FeatureKey.FINANCE, FeatureKey.LIBRARY))
        self._subscribe(self.tenant_a, plan)
        self.assertTrue(has_feature(self.tenant_a, FeatureKey.FINANCE))
        self.assertTrue(has_feature(self.tenant_a, FeatureKey.LIBRARY))
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.COMMUNICATION))

    def test_plan_name_is_irrelevant_to_entitlement(self):
        """Entitlement follows features, not the plan's name."""
        weird_name = self._plan("Gold Plus Deluxe", features=(FeatureKey.FINANCE,))
        self._subscribe(self.tenant_a, weird_name)
        self.assertTrue(has_feature(self.tenant_a, FeatureKey.FINANCE))
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.LIBRARY))

    def test_no_subscription_denies_everything(self):
        self.assertIsNone(get_active_subscription(self.tenant_a))
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.FINANCE))
        self.assertEqual(get_student_limit(self.tenant_a), 0)

    def test_inactive_subscription_denies(self):
        plan = self._plan("Premium", features=(FeatureKey.FINANCE,))
        subscription = Subscription.objects.create(
            tenant=self.tenant_a, plan=plan,
            end_date=timezone.now() + timedelta(days=30), is_active=False,
        )
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.FINANCE))
        subscription.is_active = True
        subscription.save()

    def test_expired_subscription_denies(self):
        plan = self._plan("Premium", features=(FeatureKey.FINANCE,))
        self._subscribe(self.tenant_a, plan, days=-1)
        self.assertFalse(has_feature(self.tenant_a, FeatureKey.FINANCE))

    def test_limits_are_separate_from_features(self):
        plan = self._plan("Standard", features=(FeatureKey.STUDENTS,))
        self._subscribe(self.tenant_a, plan)
        self.assertTrue(has_feature(self.tenant_a, FeatureKey.STUDENTS))
        self.assertEqual(get_student_limit(self.tenant_a), 200)

    def test_feature_gated_endpoint_403_without_subscription(self):
        """School A has no subscription -> the Finance API must refuse access."""
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("student-invoice-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)

    def test_feature_gated_endpoint_200_with_granted_feature(self):
        plan = self._plan("Premium", features=(FeatureKey.FINANCE,))
        self._subscribe(self.tenant_a, plan)
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("student-invoice-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

    def test_gated_endpoint_403_when_feature_not_in_plan(self):
        plan = self._plan("Basic", features=(FeatureKey.STUDENTS,))
        self._subscribe(self.tenant_a, plan)
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("student-invoice-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)

    def test_super_admin_bypasses_feature_gate(self):
        """Platform-level admins can audit any school regardless of its plan."""
        self.login(*self.super_admin_creds)
        response = self.client.get(
            reverse("student-invoice-list") + f"?tenant_id={self.tenant_a.tenant_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)


class SubscriptionPaymentTests(BaseTenantAPITestCase):
    """Every subscription order creates a Payment — the revenue event."""

    def _assign(self, tenant, plan=None):
        return self.client.post(
            reverse("subscription-list") + f"?tenant_id={tenant.tenant_id}",
            {"plan": plan.pk if plan else self.plan.pk},
            format="json",
        )

    def test_subscription_creation_records_initial_payment(self):
        self.login(*self.super_admin_creds)
        response = self._assign(self.tenant_a)
        self.assertEqual(response.status_code, 201, response.content)

        payment = SubscriptionPayment.objects.get(subscription__tenant=self.tenant_a)
        self.assertEqual(payment.amount, self.plan.price)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertFalse(payment.is_renewal)

    def test_plan_change_records_renewal_payment(self):
        self.login(*self.super_admin_creds)
        self._assign(self.tenant_a)

        other = Plan.objects.create(
            name="Pro", price=Decimal("3000.00"), duration_days=365,
            max_students=2000, is_active=True,
        )
        subscription = Subscription.objects.get(tenant=self.tenant_a)
        response = self.client.patch(
            reverse("subscription-detail", args=[subscription.id]),
            {"plan": other.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        renewals = SubscriptionPayment.objects.filter(subscription=subscription, is_renewal=True)
        self.assertEqual(renewals.count(), 1)
        self.assertEqual(renewals.first().amount, other.price)

    def test_renew_action_extends_and_records_payment(self):
        self.login(*self.super_admin_creds)
        subscription = Subscription.objects.create(
            tenant=self.tenant_a, plan=self.plan,
            end_date=timezone.now() - timedelta(days=1), is_active=False,
        )
        old_end = subscription.end_date

        response = self.client.post(reverse("subscription-renew", args=[subscription.id]))
        self.assertEqual(response.status_code, 200, response.content)

        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)
        self.assertGreater(subscription.end_date, old_end)

        payment = SubscriptionPayment.objects.get(subscription=subscription)
        self.assertTrue(payment.is_renewal)
        self.assertEqual(payment.amount, self.plan.price)

    def test_payments_are_scoped_to_the_callers_school(self):
        self.login(*self.super_admin_creds)
        self._assign(self.tenant_a)
        self._assign(self.tenant_b)

        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("subscription-payment-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["tenant_name"], "Alpha School")

    def test_super_admin_can_delete_a_subscription(self):
        self.login(*self.super_admin_creds)
        self._assign(self.tenant_a)

        subscription = Subscription.objects.get(tenant=self.tenant_a)
        response = self.client.delete(
            reverse("subscription-detail", args=[subscription.id])
        )
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(
            Subscription.objects.filter(tenant=self.tenant_a).exists()
        )
        self.assertFalse(
            SubscriptionPayment.objects.filter(subscription=subscription).exists()
        )


class SubscriptionListFreshnessTests(BaseTenantAPITestCase):
    """The platform subscription list must never replay a cached QuerySet.

    ``SubscriptionViewSet.get_queryset()`` used to hand back the class-level
    ``queryset`` object itself. Iterating that object fills its result cache, and
    DRF's ``filter_queryset()`` returns the very same object when no filter
    backends are configured - so the unscoped (super-admin) branch kept serving
    the rows captured by the first request. Deleting a school cascade-deletes its
    subscription, yet the platform list kept showing that ghost row until the
    worker restarted. ``.all()`` now clones the queryset per request.
    """

    def _list_subscription_ids(self):
        response = self.client.get(reverse("subscription-list"))
        self.assertEqual(response.status_code, 200, response.content)
        return [row["id"] for row in response.data]

    def test_list_sees_a_subscription_created_after_the_first_request(self):
        self.login(*self.super_admin_creds)
        self.assertEqual(self._list_subscription_ids(), [])

        subscription = self._subscribe(self.tenant_a)
        self.assertEqual(self._list_subscription_ids(), [subscription.id])

    def test_list_drops_a_school_whose_tenant_is_deleted(self):
        self.login(*self.super_admin_creds)
        subscription = self._subscribe(self.tenant_a)
        # The first request is what used to poison the shared queryset cache.
        self.assertEqual(self._list_subscription_ids(), [subscription.id])

        response = self.client.delete(
            reverse("school-profile-detail", args=[self.tenant_a.tenant_id])
        )
        self.assertEqual(response.status_code, 204, response.content)

        # The cascade really did remove the row...
        self.assertFalse(Subscription.objects.filter(tenant=self.tenant_a).exists())
        # ...and the platform list must agree, with no restart needed.
        self.assertEqual(self._list_subscription_ids(), [])


class RevenueAnalyticsTests(BaseTenantAPITestCase):
    """Platform-wide revenue summary for the super-admin dashboard."""

    def _seed(self):
        """Alpha on Basic (paid now), then an upgrade renewal to Pro; the
        initial order is moved to last month so buckets differ."""
        self.login(*self.super_admin_creds)
        self.client.post(
            reverse("subscription-list") + f"?tenant_id={self.tenant_a.tenant_id}",
            {"plan": self.plan.pk}, format="json",
        )
        pro = Plan.objects.create(
            name="Pro", price=Decimal("3000.00"), duration_days=365,
            max_students=2000, is_active=True,
        )
        subscription = Subscription.objects.get(tenant=self.tenant_a)
        self.client.patch(
            reverse("subscription-detail", args=[subscription.id]),
            {"plan": pro.pk}, format="json",
        )
        initial = SubscriptionPayment.objects.get(
            subscription__tenant=self.tenant_a, is_renewal=False
        )
        initial.payment_date = timezone.now() - timedelta(days=45)
        initial.save(update_fields=["payment_date"])
        return pro

    def test_super_admin_gets_metrics(self):
        self._seed()
        response = self.client.get(reverse("revenue-analytics"))
        self.assertEqual(response.status_code, 200, response.content)

        data = response.data
        self.assertEqual(Decimal(str(data["total_revenue"])), Decimal("3100.00"))
        self.assertEqual(data["active_subscriptions"], 1)
        self.assertEqual(data["new_subscriptions"], 1)
        self.assertEqual(data["renewals"], 1)
        self.assertEqual(data["cancelled_or_expired"], 0)
        self.assertEqual(data["school_count"], 2)  # Alpha + Beta fixtures
        self.assertEqual(data["subscription_count"], 1)

        by_month = data["revenue_by_month"]
        self.assertEqual(len(by_month), 12)
        self.assertEqual(
            sum(Decimal(str(row["revenue"])) for row in by_month), Decimal("3100.00")
        )

        by_plan = data["revenue_by_plan"]
        self.assertEqual(
            sum(Decimal(str(row["revenue"])) for row in by_plan), Decimal("3100.00")
        )
        self.assertTrue(data["recent_payments"])

    def test_tenant_admin_is_403(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("revenue-analytics"))
        self.assertEqual(response.status_code, 403, response.content)

    def test_anonymous_is_401(self):
        response = self.client.get(reverse("revenue-analytics"))
        self.assertEqual(response.status_code, 401, response.content)


class SubscriptionRequestTests(BaseTenantAPITestCase):
    """Schools request renew / plan changes; a super admin fulfils them.

    Requests never write to the live subscription directly — approval applies
    the change through the same services the admin UI uses, so the payment
    history and renewal semantics stay consistent.
    """

    def _subscribe(self, tenant, plan=None):
        return Subscription.objects.create(
            tenant=tenant,
            plan=plan or self.plan,
            end_date=timezone.now() + timedelta(days=90),
            is_active=True,
        )

    def _pro_plan(self):
        return Plan.objects.create(
            name="Pro", price=Decimal("3000.00"), duration_days=365,
            max_students=2000, is_active=True,
        )

    # ---------- creation & scoping ----------

    def test_tenant_admin_submits_renew_request(self):
        self._subscribe(self.tenant_a)
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew", "message": "Please renew for next session"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        req = SubscriptionRequest.objects.get(tenant=self.tenant_a)
        self.assertEqual(req.request_type, "renew")
        self.assertEqual(req.status, SubscriptionRequestStatus.PENDING)
        self.assertEqual(req.requested_by, self.admin_a)
        self.assertIsNone(req.plan)

    def test_change_plan_request_requires_a_target_plan(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "change_plan"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(SubscriptionRequest.objects.exists())

    def test_renew_request_rejects_an_explicit_plan(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew", "plan": self.plan.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_teacher_cannot_submit_a_request(self):
        self.login(*self.teacher_a_creds)
        response = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)

    def test_requests_are_scoped_to_the_calling_school(self):
        self.login(*self.admin_a_creds)
        self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )

        self.login(*self.admin_b_creds)
        response = self.client.get(reverse("subscription-request-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data, [])

    def test_only_one_pending_request_per_school(self):
        self.login(*self.admin_a_creds)
        first = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        self.assertEqual(first.status_code, 201, first.content)

        second = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "change_plan", "plan": self.plan.pk},
            format="json",
        )
        self.assertEqual(second.status_code, 400, second.content)

    def test_request_to_current_plan_is_rejected(self):
        pro = self._pro_plan()
        self._subscribe(self.tenant_a, pro)
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "change_plan", "plan": pro.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    # ---------- super admin approval ----------

    def test_approving_renew_applies_and_records_payment(self):
        self._subscribe(self.tenant_a)
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        request_id = created.data["id"]

        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("subscription-request-approve", args=[request_id]),
            {"notes": "Approved"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        req = SubscriptionRequest.objects.get(id=request_id)
        self.assertEqual(req.status, SubscriptionRequestStatus.APPROVED)
        self.assertEqual(req.processed_by, self.super_admin)
        self.assertEqual(req.admin_notes, "Approved")

        subscription = Subscription.objects.get(tenant=self.tenant_a)
        self.assertTrue(subscription.is_active)
        payment = SubscriptionPayment.objects.get(
            subscription=subscription, is_renewal=True
        )
        self.assertEqual(payment.amount, subscription.plan.price)

    def test_approving_change_plan_switches_plan(self):
        self._subscribe(self.tenant_a)
        pro = self._pro_plan()
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "change_plan", "plan": pro.pk},
            format="json",
        )
        request_id = created.data["id"]

        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("subscription-request-approve", args=[request_id]), format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        subscription = Subscription.objects.get(tenant=self.tenant_a)
        self.assertEqual(subscription.plan, pro)
        payment = SubscriptionPayment.objects.get(
            subscription=subscription, is_renewal=True
        )
        self.assertEqual(payment.amount, pro.price)

    def test_approve_without_a_subscription_is_a_clean_400(self):
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        request_id = created.data["id"]

        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("subscription-request-approve", args=[request_id]), format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        req = SubscriptionRequest.objects.get(id=request_id)
        self.assertEqual(req.status, SubscriptionRequestStatus.PENDING)

    def test_reject_leaves_subscription_untouched(self):
        subscription = self._subscribe(self.tenant_a)
        old_end = subscription.end_date
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        request_id = created.data["id"]

        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("subscription-request-reject", args=[request_id]),
            {"notes": "Rejected"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        req = SubscriptionRequest.objects.get(id=request_id)
        self.assertEqual(req.status, SubscriptionRequestStatus.REJECTED)

        subscription.refresh_from_db()
        self.assertEqual(subscription.end_date, old_end)
        self.assertFalse(
            SubscriptionPayment.objects.filter(
                subscription=subscription, is_renewal=True
            ).exists()
        )

    def test_super_admin_lists_all_schools_requests(self):
        self.login(*self.admin_a_creds)
        self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        self.login(*self.admin_b_creds)
        self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )

        self.login(*self.super_admin_creds)
        response = self.client.get(reverse("subscription-request-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 2)

    # ---------- cancellation ----------

    def test_school_cancels_its_own_pending_request(self):
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        request_id = created.data["id"]

        response = self.client.post(
            reverse("subscription-request-cancel", args=[request_id]), format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        req = SubscriptionRequest.objects.get(id=request_id)
        self.assertEqual(req.status, SubscriptionRequestStatus.CANCELLED)

    def test_school_cannot_cancel_another_schools_request(self):
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("subscription-request-list"),
            {"request_type": "renew"}, format="json",
        )
        request_id = created.data["id"]

        self.login(*self.admin_b_creds)
        response = self.client.post(
            reverse("subscription-request-cancel", args=[request_id]), format="json",
        )
        self.assertEqual(response.status_code, 404, response.content)


class MyPlanViewTests(BaseTenantAPITestCase):
    """Sidebar gating payload: any tenant member reads their school's
    plan entitlements so locked navigation shows an upgrade prompt."""

    def _plan(self, name, features=()):
        plan = Plan.objects.create(
            name=name, price=100, duration_days=30,
            max_students=200, is_active=True,
        )
        plan.features.set([
            Feature.objects.get_or_create(key=key, defaults={"name": key.label})[0]
            for key in features
        ])
        return plan

    def test_tenant_admin_reads_own_plan_features(self):
        self.login(*self.admin_a_creds)
        self._subscribe(self.tenant_a)
        response = self.client.get(reverse("my-plan"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["plan_name"], "Basic")
        self.assertIn(FeatureKey.FINANCE, response.data["plan_features"])
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.data["max_students"], 500)

    def test_only_granted_features_are_returned(self):
        self.login(*self.admin_a_creds)
        plan = self._plan("Starter", features=(FeatureKey.STUDENTS, FeatureKey.ACADEMICS))
        self._subscribe(self.tenant_a, plan)
        response = self.client.get(reverse("my-plan"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data["plan_features"]),
            {FeatureKey.STUDENTS, FeatureKey.ACADEMICS},
        )

    def test_no_subscription_returns_empty_entitlement(self):
        self.login(*self.admin_a_creds)
        response = self.client.get(reverse("my-plan"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["plan"])
        self.assertEqual(response.data["plan_features"], [])
        self.assertFalse(response.data["is_active"])

    def test_expired_subscription_returns_inactive(self):
        self.login(*self.admin_a_creds)
        self._subscribe(self.tenant_a)
        Subscription.objects.filter(tenant=self.tenant_a).update(
            end_date=timezone.now() - timedelta(days=1)
        )
        response = self.client.get(reverse("my-plan"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])

    def test_non_admin_member_may_read_plan(self):
        """Teacher (not admin/principal) can read school plan entitlements."""
        self.login(*self.teacher_a_creds)
        self._subscribe(self.tenant_a)
        response = self.client.get(reverse("my-plan"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["plan_name"], "Basic")

    def test_super_admin_without_tenant_gets_empty_entitlement(self):
        self.login(*self.super_admin_creds)
        response = self.client.get(reverse("my-plan"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.data["plan"])
        self.assertEqual(response.data["plan_features"], [])


class PlanFeatureManagementTests(BaseTenantAPITestCase):
    """The super admin grants a plan's features from the Plans screen.

    ``features`` is the list of FeatureKey strings a plan unlocks — the same
    keys the sidebar locks and every ``HasFeatureAccess`` view checks (``finance``
    is what gates the Fees page). It therefore has to be writable through the
    API, and only by the super admin.
    """

    def _feature(self, key):
        feature, _ = Feature.objects.get_or_create(key=key, defaults={"name": key.label})
        return feature

    def _plan(self, name="Standard", features=()):
        plan = Plan.objects.create(
            name=name, price=Decimal("1000.00"), duration_days=365, max_students=400
        )
        plan.features.set([self._feature(key) for key in features])
        return plan

    def test_super_admin_creates_a_plan_with_features(self):
        self.login(*self.super_admin_creds)
        response = self.client.post(
            reverse("plan-list"),
            {
                "name": "Finance Plan",
                "price": "1500.00",
                "duration_days": 365,
                "max_students": 300,
                "features": [FeatureKey.STUDENTS, FeatureKey.FINANCE],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        plan = Plan.objects.get(name="Finance Plan")
        self.assertEqual(plan.feature_keys(), {FeatureKey.STUDENTS, FeatureKey.FINANCE})
        self.assertEqual(
            sorted(response.data["features"]),
            sorted([FeatureKey.STUDENTS, FeatureKey.FINANCE]),
        )

    def test_super_admin_adds_finance_to_an_existing_plan(self):
        plan = self._plan(features=(FeatureKey.STUDENTS,))
        self.login(*self.super_admin_creds)
        response = self.client.patch(
            reverse("plan-detail", args=[plan.pk]),
            {"features": [FeatureKey.STUDENTS, FeatureKey.FINANCE]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        plan.refresh_from_db()
        self.assertEqual(plan.feature_keys(), {FeatureKey.STUDENTS, FeatureKey.FINANCE})

    def test_features_are_kept_when_not_sent_and_clearable(self):
        plan = self._plan(features=(FeatureKey.FINANCE,))
        self.login(*self.super_admin_creds)

        # A plain price edit leaves the feature set alone...
        kept = self.client.patch(
            reverse("plan-detail", args=[plan.pk]), {"price": "1200.00"}, format="json"
        )
        self.assertEqual(kept.status_code, 200, kept.content)
        plan.refresh_from_db()
        self.assertEqual(plan.feature_keys(), {FeatureKey.FINANCE})

        # ...while an explicit empty list clears it.
        cleared = self.client.patch(
            reverse("plan-detail", args=[plan.pk]), {"features": []}, format="json"
        )
        self.assertEqual(cleared.status_code, 200, cleared.content)
        plan.refresh_from_db()
        self.assertEqual(plan.feature_keys(), set())

    def test_unknown_feature_key_is_a_clean_400(self):
        plan = self._plan(features=(FeatureKey.FINANCE,))
        self.login(*self.super_admin_creds)
        response = self.client.patch(
            reverse("plan-detail", args=[plan.pk]),
            {"features": ["not-a-feature"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("features", response.data)
        plan.refresh_from_db()
        self.assertEqual(plan.feature_keys(), {FeatureKey.FINANCE})

    def test_tenant_admin_cannot_change_plan_features(self):
        plan = self._plan()
        self.login(*self.admin_a_creds)
        created = self.client.post(
            reverse("plan-list"),
            {"name": "Rogue", "price": "1.00", "features": [FeatureKey.FINANCE]},
            format="json",
        )
        self.assertEqual(created.status_code, 403, created.content)

        updated = self.client.patch(
            reverse("plan-detail", args=[plan.pk]),
            {"features": [FeatureKey.FINANCE]},
            format="json",
        )
        self.assertEqual(updated.status_code, 403, updated.content)
        plan.refresh_from_db()
        self.assertEqual(plan.feature_keys(), set())

    def test_granting_finance_unblocks_the_school(self):
        """End to end: tick Finance on the plan and the Fees API opens up."""
        plan = self._plan(features=(FeatureKey.STUDENTS,))
        Subscription.objects.create(
            tenant=self.tenant_b,
            plan=plan,
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
        )
        self.assertFalse(has_feature(self.tenant_b, FeatureKey.FINANCE))

        self.login(*self.admin_b_creds)
        self.assertEqual(self.client.get(reverse("fee-type-list")).status_code, 403)

        self.login(*self.super_admin_creds)
        response = self.client.patch(
            reverse("plan-detail", args=[plan.pk]),
            {"features": [FeatureKey.STUDENTS, FeatureKey.FINANCE]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(has_feature(self.tenant_b, FeatureKey.FINANCE))

        # The school's admin can now create the fee type the dialog offers.
        self.login(*self.admin_b_creds)
        created = self.client.post(
            reverse("fee-type-list"), {"name": "Tuition Fee"}, format="json"
        )
        self.assertEqual(created.status_code, 201, created.content)