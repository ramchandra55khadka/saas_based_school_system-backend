from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user_account', '0003_tenantmembership_uuid_useraccount_uuid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='useraccount',
            name='phone',
        ),
    ]
