"""Copy legacy rows from the removed ``fees`` app into ``finance`` tables.

The ``fees`` app was consolidated into ``finance``.  Its tables outlive the
app removal (Django never drops them automatically), so on existing databases
we move the rows over.  On fresh databases the ``fees_*`` tables do not exist
and this migration is a no-op.

The columns are copied verbatim (including PK ``id`` and the ``uuid`` column),
so every FK/report still points at the same logical records.
"""

from django.db import migrations


# (legacy table, finance table, columns to copy)
_MOVE = {
    'fees_feetype': ('finance_feetype', [
        'id', 'uuid', 'created_at', 'updated_at', 'tenant_id', 'name', 'description',
    ]),
    'fees_feestructure': ('finance_feestructure', [
        'id', 'uuid', 'created_at', 'updated_at', 'tenant_id',
        'fee_type_id', 'academic_year_id', 'school_class_id', 'amount',
    ]),
    'fees_studentinvoice': ('finance_studentinvoice', [
        'id', 'uuid', 'created_at', 'updated_at', 'tenant_id',
        'student_id', 'title', 'academic_year_id', 'total_amount', 'due_date', 'status',
    ]),
    'fees_feepayment': ('finance_feepayment', [
        'id', 'uuid', 'created_at', 'updated_at', 'tenant_id',
        'invoice_id', 'amount_paid', 'payment_date', 'payment_method',
        'receipt_number', 'transaction_id', 'remarks',
    ]),
}

# Business-unique keys on the new tables.  Rows whose key already exists in the
# target are skipped so that duplicate legacy rows can never crash the migrate.
_KEY_COLUMNS = {
    'finance_feetype': ['tenant_id', 'name'],
    'finance_feestructure': ['fee_type_id', 'academic_year_id', 'school_class_id'],
}


def copy_legacy_rows(apps, schema_editor):
    connection = schema_editor.connection
    cursor = connection.cursor()
    table_names = set(connection.introspection.table_names())

    for legacy_table, (finance_table, columns) in _MOVE.items():
        if legacy_table not in table_names or finance_table not in table_names:
            continue

        # Only copy columns that actually exist in the legacy table.
        legacy_columns = {
            col.name
            for col in connection.introspection.get_table_description(cursor, legacy_table)
        }
        columns = [c for c in columns if c in legacy_columns]
        if not columns:
            continue

        quoted = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))

        cursor.execute(f'SELECT {quoted} FROM {legacy_table}')
        source_rows = cursor.fetchall()

        cursor.execute(f'SELECT id FROM {finance_table}')
        existing_ids = {row[0] for row in cursor.fetchall()}

        key_columns = [c for c in _KEY_COLUMNS.get(finance_table, []) if c in columns]
        existing_keys = set()
        if key_columns:
            cursor.execute(f'SELECT {", ".join(key_columns)} FROM {finance_table}')
            existing_keys = {tuple(row) for row in cursor.fetchall()}

        key_idxs = [columns.index(col) for col in key_columns]

        for row in source_rows:
            if row[0] in existing_ids:
                continue
            if key_columns and tuple(row[i] for i in key_idxs) in existing_keys:
                continue
            cursor.execute(
                f'INSERT INTO {finance_table} ({quoted}) VALUES ({placeholders})',
                list(row),
            )
            existing_ids.add(row[0])
            if key_columns:
                existing_keys.add(tuple(row[i] for i in key_idxs))


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copy_legacy_rows, migrations.RunPython.noop),
    ]