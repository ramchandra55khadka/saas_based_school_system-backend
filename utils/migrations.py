"""Helpers for schema migrations."""

import copy
import uuid

from django.db import migrations


class AddUUIDField(migrations.AddField):
    """``AddField`` for the ``AbstractUUID.uuid`` column, backfill-safe.

    A plain ``AddField`` evaluates its callable default **once**, so every
    existing row would receive the same uuid and the unique constraint would
    blow up on any populated table. This operation instead:

    1. adds the column nullable and without the unique index,
    2. backfills one distinct uuid per existing row,
    3. re-creates the column ``NOT NULL`` + unique to match the model state.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model(schema_editor.connection.alias, model):
            # Base the temporary column on the *rendered* field, which carries
            # the attributes (e.g. ``column``) the schema editor relies on.
            field = model._meta.get_field(self.name)
            nullable = copy.deepcopy(field)
            nullable.null = True
            nullable.unique = False
            nullable.db_index = False
            # Strip the default as well: PostgreSQL would otherwise apply the
            # callable default to every existing row (one shared value), even
            # for a nullable column, which the backfill below couldn't fix.
            nullable.default = None
            schema_editor.add_field(model, nullable)

            # One distinct uuid per existing row (queryset.update() bypasses
            # model.save() side effects, e.g. FeePayment's receipt logic).
            manager = model._default_manager.using(schema_editor.connection.alias)
            for row in manager.filter(uuid__isnull=True).only('pk'):
                manager.filter(pk=row.pk).update(uuid=uuid.uuid4())

            schema_editor.alter_field(model, nullable, field)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model(schema_editor.connection.alias, model):
            schema_editor.remove_field(model, model._meta.get_field(self.name))
