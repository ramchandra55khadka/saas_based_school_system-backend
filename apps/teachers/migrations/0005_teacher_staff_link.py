"""Teacher.user_profile -> Teacher.staff.

``UserProfile`` is OneToOne with ``staff.Staff``, so the teacher record now
hangs off the staff record instead of duplicating the profile link.

Data-preserving path: each teacher's ``Staff`` row is found via the old
``user_profile_id`` (matched within the same tenant); an account that had no
staff record yet gets one backfilled as a teacher designation so the
NOT NULL added afterwards cannot fail.
"""
import django.db.models.deletion
from django.db import migrations, models


def _flush_deferred_constraints(schema_editor):
    """Fire queued deferred FK checks before the DDL that follows.

    PostgreSQL defers Django's FK checks until COMMIT, so the rows written
    below leave *pending trigger events* on the referenced tables. Any
    ``ALTER TABLE`` touching those tables later in the same transaction then
    fails with ``cannot ALTER TABLE ... because it has pending trigger
    events`` - dropping the ``staff.staff`` FK below also cleans up the RI
    triggers PostgreSQL keeps on ``staff_staff`` itself. Forcing the
    constraints immediate flushes that queue (the same trick Django's own
    PostgreSQL DDL uses via ``SET CONSTRAINTS "<fk>" IMMEDIATE``).
    """
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


def link_teachers_to_staff(apps, schema_editor):
    Teacher = apps.get_model('teachers', 'Teacher')
    Staff = apps.get_model('staff', 'Staff')
    for teacher in Teacher.objects.all().iterator():
        staff = (
            Staff.objects.filter(
                user_profile_id=teacher.user_profile_id,
                tenant_id=teacher.tenant_id,
            ).first()
            or Staff.objects.filter(user_profile_id=teacher.user_profile_id).first()
        )
        if staff is None:
            staff_kwargs = {
                'tenant_id': teacher.tenant_id,
                'user_profile_id': teacher.user_profile_id,
            }
            staff_field_names = {field.name for field in Staff._meta.fields}
            if 'designation' in staff_field_names:
                staff_kwargs['designation'] = 'teacher'
            else:
                staff_kwargs['staff_type'] = 'teacher'
            staff = Staff.objects.create(**staff_kwargs)
        teacher.staff_id = staff.pk
        teacher.save(update_fields=['staff_id'])
    _flush_deferred_constraints(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0004_teacher_rename_and_user_profile_link'),
        ('staff', '0004_rename_staffprofile_staff'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacher',
            name='staff',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teachers',
                to='staff.staff',
            ),
        ),
        migrations.RunPython(link_teachers_to_staff, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='teacher',
            name='staff',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teachers',
                to='staff.staff',
            ),
        ),
        migrations.RemoveField(model_name='teacher', name='user_profile'),
        migrations.AlterModelOptions(
            name='teacher',
            options={
                'ordering': [
                    'staff__user_profile__first_name',
                    'staff__user_profile__last_name',
                ],
                'verbose_name': 'Teacher',
                'verbose_name_plural': 'Teachers',
            },
        ),
    ]
