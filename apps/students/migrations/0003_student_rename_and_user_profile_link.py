"""Rename ``StudentProfile`` to ``Student`` and hang it off ``UserProfile``.

``StudentProfile`` used to be linked straight to the ``UserAccount`` and carried
the student's identity columns (``date_of_birth``, ``address``) plus three
denormalised guardian columns. Personal identity now lives on
``user_profile.UserProfile`` and guardianship is modelled properly by
``parents.Parent`` + ``parents.StudentGuardian``.

The model is **renamed**, not recreated, so ``students_studentprofile`` becomes
``students_student`` with its rows and every inbound FK (``fees``, ``library``,
``examresult``, ``studentattendance``, ``studentdocument``,
``studentpromotion``) still pointing at the same table — no data is dropped and
no dependent row is orphaned.

Data carried over:

* ``user.profile`` -> ``Student.user_profile``
* ``date_of_birth``/``address`` -> the linked ``UserProfile`` (only where blank)
* ``roll_number`` -> coerced from text to integer (``"10A-07"`` -> ``7``)

The legacy ``guardian_name``/``guardian_phone``/``guardian_relation`` columns are
dropped: one text column cannot express a many-to-many guardianship, and the
demo seed rebuilds them as a real ``Parent`` + ``StudentGuardian`` pair.
"""
import re

import django.db.models.deletion
from django.db import migrations, models


def _coerce_roll_number(raw):
    """``"10A-07"`` -> ``7``; unparseable values become ``None``."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    groups = re.findall(r'\d+', str(raw))
    if not groups:
        return None
    return int(groups[-1])


def _drop_colliding_roll_numbers(apps):
    """Reset duplicates before ``unique_student_roll_per_section`` is added.

    Two different legacy strings can coerce to the same integer (``"07"`` and
    ``"10A-07"``). The constraint only applies to non-null rolls, so the later
    duplicates are nulled rather than deleted.
    """
    Student = apps.get_model('students', 'Student')
    seen = set()
    for student in Student.objects.filter(roll_number__isnull=False).order_by('pk').iterator():
        key = (student.tenant_id, student.school_class_id, student.section_id, student.roll_number)
        if key in seen:
            Student.objects.filter(pk=student.pk).update(roll_number=None)
        else:
            seen.add(key)


def link_students_to_user_profiles(apps, schema_editor):
    """Point every student at its ``UserProfile`` and migrate free-text data."""
    Student = apps.get_model('students', 'Student')
    UserProfile = apps.get_model('user_profile', 'UserProfile')

    for student in Student.objects.all().iterator():
        if not student.user_id:
            continue

        profile = UserProfile.objects.filter(user_account_id=student.user_id).first()

        # Defensive: an account with no profile should never exist (the
        # user_account profile migration backfills one), but a student row
        # without a profile would break the NOT NULL added later.
        if profile is None:
            account = apps.get_model('user_account', 'UserAccount')
            username = (
                account.objects.filter(pk=student.user_id)
                .values_list('username', flat=True)
                .first()
            )
            profile = UserProfile.objects.create(
                user_account_id=student.user_id,
                first_name=username or '',
            )

        student.user_profile_id = profile.pk

        # Roll numbers were free text ("10A-07"); Student.roll_number is a
        # PositiveIntegerField. The last digit group is the roll part in every
        # observed format.
        student.roll_number = _coerce_roll_number(student.roll_number)

        # Identity columns that moved to UserProfile: fill blanks only, so a
        # value already maintained on the profile wins.
        profile_updates = []
        if student.date_of_birth and not profile.date_of_birth:
            profile.date_of_birth = student.date_of_birth
            profile_updates.append('date_of_birth')
        if student.address and not profile.address:
            profile.address = student.address
            profile_updates.append('address')
        if profile_updates:
            profile.save(update_fields=profile_updates)

        student.save(update_fields=['user_profile', 'roll_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0002_exam_uuid_examresult_uuid_studentattendance_uuid_and_more'),
        ('user_profile', '0001_initial'),
    ]

    operations = [
        # 1. Rename the model rather than recreating it: every inbound FK
        #    (fees.StudentInvoice, library.LibraryMember, ExamResult,
        #    StudentAttendance, StudentDocument, StudentPromotion) keeps pointing
        #    at the same table, so no dependent row is orphaned.
        migrations.RenameModel(old_name='StudentProfile', new_name='Student'),
        migrations.AlterModelOptions(
            name='student',
            options={
                'verbose_name': 'Student',
                'verbose_name_plural': 'Students',
                'ordering': ['school_class', 'section', 'roll_number'],
            },
        ),
        # 2. Swap the UserAccount FK for the UserProfile O2O. Added nullable so
        #    existing rows survive, backfilled, then tightened to NOT NULL.
        migrations.AddField(
            model_name='student',
            name='user_profile',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student',
                to='user_profile.userprofile',
            ),
        ),
        # 3. roll_number becomes nullable *before* the backfill runs: an
        #    unparseable or empty legacy value must be able to become NULL, and
        #    the column is NOT NULL at this point. The type change to
        #    PositiveIntegerField happens after the data is normalised.
        migrations.AlterField(
            model_name='student',
            name='roll_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        # 4. Backfill *before* the columns below are dropped:
        #    link_students_to_user_profiles() copies date_of_birth/address onto
        #    the linked UserProfile and coerces the free-text roll numbers, so it
        #    needs the legacy columns and the new (nullable) FK to both exist.
        migrations.RunPython(link_students_to_user_profiles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='student',
            name='user_profile',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student',
                to='user_profile.userprofile',
            ),
        ),
        migrations.RemoveField(model_name='student', name='user'),
        # 5. Identity columns and the denormalised guardian columns go away:
        #    identity lives on UserProfile, guardianship on parents.StudentGuardian.
        migrations.RemoveField(model_name='student', name='date_of_birth'),
        migrations.RemoveField(model_name='student', name='address'),
        migrations.RemoveField(model_name='student', name='guardian_name'),
        migrations.RemoveField(model_name='student', name='guardian_phone'),
        migrations.RemoveField(model_name='student', name='guardian_relation'),
        # 5. Text roll numbers are now integers ("10A-07" -> 7, NULL when the
        #    legacy value carried no digits).
        migrations.AlterField(
            model_name='student',
            name='roll_number',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='student',
            name='blood_group',
            field=models.CharField(blank=True, max_length=10),
        ),
        # related_name='students' became ambiguous once user_profile.Student
        # existed; both FKs now use 'profile_students'.
        migrations.AlterField(
            model_name='student',
            name='school_class',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='profile_students',
                to='academics.class',
            ),
        ),
        migrations.AlterField(
            model_name='student',
            name='section',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='profile_students',
                to='academics.section',
            ),
        ),
        # 6. One roll number per section (ignoring rows without one).
        #
        # STATE-ONLY: the identically-named constraint still exists on
        # user_profile_student (the legacy user_profile.Student table) at this
        # point, and Postgres constraint names are schema-wide, so adding it to
        # the DB here would collide. students/0004 adds the real constraint
        # after user_profile/0003 has dropped that table.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddConstraint(
                    model_name='student',
                    constraint=models.UniqueConstraint(
                        condition=models.Q(('roll_number__isnull', False)),
                        fields=('tenant', 'school_class', 'section', 'roll_number'),
                        name='unique_student_roll_per_section',
                    ),
                ),
            ],
        ),
    ]
