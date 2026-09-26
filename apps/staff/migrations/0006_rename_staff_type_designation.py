from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('staff', '0005_alter_staff_options'),
    ]

    operations = [
        migrations.RenameField(
            model_name='staff',
            old_name='staff_type',
            new_name='designation',
        ),
    ]
