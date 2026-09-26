"""UserProfile timestamps come from ``AbstractCreatedAtModifiedAt``.

``created_at`` changes from ``auto_now_add`` to ``default=now`` (same effect
on insert, but explicit values are now honoured) and gains a db index.
``updated_at`` (``auto_now``) is renamed to the abstract's ``modified_at`` —
renamed, not dropped, so existing timestamps survive; it stops auto-updating
per the abstract's definition (``editable=False``, ``blank/null``, indexed).
"""
from django.db import migrations, models
from django.utils.timezone import now


class Migration(migrations.Migration):

    dependencies = [
        ('user_profile', '0003_remove_studentguardian_parent_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='created_at',
            field=models.DateTimeField(db_index=True, default=now, editable=False),
        ),
        migrations.RenameField(
            model_name='userprofile', old_name='updated_at', new_name='modified_at',
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='modified_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True, editable=False),
        ),
    ]
