"""Add ``unique_student_roll_per_section`` to the real database.

The constraint is already part of the migration **state** (students/0003
registered it state-only): the legacy ``user_profile_student`` table still held
a constraint of the same name when 0003 ran, and Postgres constraint names are
schema-wide. This migration runs after user_profile/0003 has dropped that
table, so the name is free again.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0003_student_rename_and_user_profile_link'),
        ('user_profile', '0003_remove_studentguardian_parent_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='student',
            constraint=models.UniqueConstraint(
                condition=models.Q(('roll_number__isnull', False)),
                fields=('tenant', 'school_class', 'section', 'roll_number'),
                name='unique_student_roll_per_section',
            ),
        ),
    ]
