from django.db import migrations


def _flush_deferred_constraints(schema_editor):
    """Fire queued deferred FK checks before the DDL that follows.

    This migration writes to ``staff_staff`` and ``user_profile_userprofile``;
    because PostgreSQL defers Django's FK checks to COMMIT, those writes leave
    pending trigger events on both tables, which the ``RemoveField`` DDL below
    trips over (dropping an FK also clears the RI triggers on the referenced
    table). See ``0005_teacher_staff_link`` for the same pattern.
    """
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


def move_teacher_details_to_staff(apps, schema_editor):
    Teacher = apps.get_model('teachers', 'Teacher')

    for teacher in Teacher.objects.select_related('staff', 'staff__user_profile').all().iterator():
        staff = teacher.staff
        profile = staff.user_profile

        staff_updates = []
        for field in ['employee_id', 'qualification', 'specialization', 'date_of_joining']:
            value = getattr(teacher, field, None)
            if value and not getattr(staff, field):
                setattr(staff, field, value)
                staff_updates.append(field)
        if staff_updates:
            staff.save(update_fields=staff_updates)

        profile_updates = []
        for field in ['phone', 'address']:
            value = getattr(teacher, field, None)
            if value and not getattr(profile, field):
                setattr(profile, field, value)
                profile_updates.append(field)
        if profile_updates:
            profile.save(update_fields=profile_updates)

    _flush_deferred_constraints(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0005_teacher_staff_link'),
    ]

    operations = [
        migrations.RunPython(move_teacher_details_to_staff, migrations.RunPython.noop),
        migrations.RemoveField(model_name='teacher', name='employee_id'),
        migrations.RemoveField(model_name='teacher', name='qualification'),
        migrations.RemoveField(model_name='teacher', name='specialization'),
        migrations.RemoveField(model_name='teacher', name='date_of_joining'),
        migrations.RemoveField(model_name='teacher', name='phone'),
        migrations.RemoveField(model_name='teacher', name='address'),
    ]
