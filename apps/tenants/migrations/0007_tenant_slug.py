from django.db import migrations, models
from django.utils.text import slugify


def backfill_tenant_slugs(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    used = set()

    for tenant in Tenant.objects.order_by('tenant_name', 'tenant_id'):
        base = slugify(tenant.tenant_name) or slugify(tenant.org_code) or str(tenant.tenant_id)
        slug = base[:120]
        counter = 2
        while slug in used:
            suffix = f'-{counter}'
            slug = f'{base[:120 - len(suffix)]}{suffix}'
            counter += 1
        tenant.slug = slug
        tenant.save(update_fields=['slug'])
        used.add(slug)


class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0006_alter_department_level'),
    ]

    operations = [
        # db_index=False is load-bearing, do not "clean it up".
        #
        # SlugField defaults to db_index=True, which makes the Postgres backend
        # queue a `varchar_pattern_ops` index in the schema editor's deferred
        # SQL. The AlterField below turns on unique=True, and Postgres's
        # _alter_field creates that very same `_like` index eagerly. Both live
        # in one atomic migration, so the deferred copy is flushed afterwards and
        # the migration dies with:
        #
        #   ProgrammingError: relation "tenants_tenant_slug_0a9b71e6_like"
        #   already exists
        #
        # because the whole migration rolls back, the column never lands and the
        # failure repeats on every `migrate`. Opting this intermediate field out
        # of indexing leaves the final AlterField to create exactly one index.
        migrations.AddField(
            model_name='tenant',
            name='slug',
            field=models.SlugField(blank=True, db_index=False, max_length=120),
        ),
        migrations.RunPython(backfill_tenant_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='tenant',
            name='slug',
            field=models.SlugField(max_length=120, unique=True),
        ),
    ]
