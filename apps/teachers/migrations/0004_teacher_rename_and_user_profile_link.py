"""TeacherProfile -> Teacher rename, profile-based redesign.

Same data-preserving patterns as the students app migration:

* the table is **renamed** (``teachers_teacherprofile`` -> ``teachers_teacher``)
  so attendance rows and leave requests keep pointing at the same rows;
* ``user`` (OneToOne to the login account) is replaced by ``user_profile``
  (OneToOne to ``user_profile.UserProfile``), resolved through
  ``UserProfile.user_account`` — an account without a profile gets one
  backfilled so the NOT NULL added afterwards cannot fail;
* ``date_of_birth`` moves to the linked UserProfile (it already lives there);
  ``phone`` / ``address`` are mirrored onto the profile where blank;
* ordering moves from ``user__username`` to the profile's name columns.
"""
import django.db.models.deletion
from django.db import migrations, models


def link_teachers_to_user_profiles(apps, schema_editor):
    Teacher = apps.get_model('teachers', 'Teacher')
    UserProfile = apps.get_model('user_profile', 'UserProfile')
    UserAccount = apps.get_model('user_account', 'UserAccount')

    for teacher in Teacher.objects.all().iterator():
        profile = UserProfile.objects.filter(user_account_id=teacher.user_id).first()
        if profile is None:
            username = (
                UserAccount.objects.filter(pk=teacher.user_id)
                .values_list('username', flat=True)
                .first()
            )
            profile = UserProfile.objects.create(
                user_account_id=teacher.user_id,
                first_name=username or '',
            )
        teacher.user_profile_id = profile.pk

        # Mirror identity onto the profile where the profile is still blank;
        # a value already maintained on the profile wins.
        profile_updates = []
        if teacher.date_of_birth and not profile.date_of_birth:
            profile.date_of_birth = teacher.date_of_birth
            profile_updates.append('date_of_birth')
        if teacher.phone and not profile.phone:
            profile.phone = teacher.phone
            profile_updates.append('phone')
        if teacher.address and not profile.address:
            profile.address = teacher.address
            profile_updates.append('address')
        if profile_updates:
            profile.save(update_fields=profile_updates)
        teacher.save(update_fields=['user_profile_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0003_leaverequest_uuid_teacherattendance_uuid_and_more'),
        ('user_profile', '0002_parent_uuid_student_uuid_studentguardian_uuid_and_more'),
    ]

    operations = [
        migrations.RenameModel(old_name='TeacherProfile', new_name='Teacher'),
        migrations.AddField(
            model_name='teacher',
            name='user_profile',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teacher',
                to='user_profile.userprofile',
            ),
        ),
        migrations.RunPython(link_teachers_to_user_profiles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='teacher',
            name='user_profile',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teacher',
                to='user_profile.userprofile',
            ),
        ),
        migrations.RemoveField(model_name='teacher', name='user'),
        migrations.RemoveField(model_name='teacher', name='date_of_birth'),
        migrations.AlterModelOptions(
            name='teacher',
            options={
                'ordering': ['user_profile__first_name', 'user_profile__last_name'],
                'verbose_name': 'Teacher',
                'verbose_name_plural': 'Teachers',
            },
        ),
    ]
