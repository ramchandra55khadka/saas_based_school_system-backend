"""Backfill a payment for every existing subscription.

Subscriptions created before SubscriptionPayment existed have no order record;
give each one a paid payment matching the plan price at its start date so the
super-admin revenue dashboard immediately reflects historical data instead of
starting from zero.
"""
from django.db import migrations


def backfill_payments(apps, schema_editor):
    Subscription = apps.get_model('subscription', 'Subscription')
    SubscriptionPayment = apps.get_model('subscription', 'SubscriptionPayment')

    for subscription in Subscription.objects.select_related('plan').all():
        SubscriptionPayment.objects.get_or_create(
            subscription=subscription,
            is_renewal=False,
            defaults={
                'plan': subscription.plan,
                'amount': subscription.plan.price,
                'status': 'paid',
                'payment_date': subscription.start_date,
            },
        )


def remove_backfilled(apps, schema_editor):
    SubscriptionPayment = apps.get_model('subscription', 'SubscriptionPayment')
    SubscriptionPayment.objects.filter(is_renewal=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0009_subscriptionpayment'),
    ]

    operations = [
        migrations.RunPython(backfill_payments, remove_backfilled),
    ]