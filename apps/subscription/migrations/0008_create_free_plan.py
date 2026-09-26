from decimal import Decimal

from django.db import migrations


FREE_PLAN_FEATURES = {
    "students": "Students",
    "teachers": "Teachers",
    "academics": "Academics",
    "reports": "Reports",
}


def create_free_plan(apps, schema_editor):
    """Create the demo/trial Free plan (price 0, tiny student cap).

    Plans are otherwise created by super admins in the database; the Free plan
    is special because every new deployment needs it for trials.
    """
    Plan = apps.get_model("subscription", "Plan")
    Feature = apps.get_model("subscription", "Feature")

    features = {}
    for key, name in FREE_PLAN_FEATURES.items():
        feature, _ = Feature.objects.get_or_create(key=key, defaults={"name": name})
        features[key] = feature

    plan, _ = Plan.objects.get_or_create(
        name="Free",
        defaults={
            "price": Decimal("0.00"),
            "duration_days": 30,
            "max_students": 10,
            "is_active": True,
        },
    )
    plan.features.set([features[key] for key in FREE_PLAN_FEATURES])


def remove_free_plan(apps, schema_editor):
    Plan = apps.get_model("subscription", "Plan")
    Plan.objects.filter(name="Free").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscription", "0007_remove_plan_reports_tier"),
    ]

    operations = [
        migrations.RunPython(create_free_plan, remove_free_plan),
    ]