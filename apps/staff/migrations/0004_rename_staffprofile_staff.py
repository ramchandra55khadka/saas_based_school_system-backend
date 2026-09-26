"""StaffProfile -> Staff rename.

The model is renamed, not recreated, so ``staff_staffprofile`` becomes
``staff_staff`` and every inbound FK (``library.LibraryMember.staff``,
``library.BookIssue.issued_by``) keeps pointing at the same rows. The
``user_profile`` reverse accessor is renamed from ``staff_profile`` to
``staff`` to match ``profile.student`` / ``profile.parent`` / ``profile.teacher``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staff', '0003_staffprofile_uuid'),
    ]

    operations = [
        migrations.RenameModel(old_name='StaffProfile', new_name='Staff'),
        migrations.AlterField(
            model_name='staff',
            name='user_profile',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='staff',
                to='user_profile.userprofile',
            ),
        ),
    ]
