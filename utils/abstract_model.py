from django.conf import settings
from django.db import models
from django.utils.timezone import now
import uuid


class AbstractActiveModel(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class AbstractUUID(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, unique=True)

    class Meta:
        abstract = True


class AbstractTimeStampedModel(models.Model):
    """
    Abstract base providing created_at and an auto-maintained updated_at.
    ``created_at`` keeps ``default=now`` so explicit values are honoured on
    insert; ``updated_at`` uses ``auto_now`` and is always refreshed on save.
    """
    created_at = models.DateTimeField(default=now, db_index=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class AbstractCreatedByModifiedBy(models.Model):
    """
    This is an abstract class which provide created_by and modified_by UserFields
    """
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        editable=False,
        related_name='created_%(app_label)s_%(class)s',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        editable=False,
        related_name='modified_%(app_label)s_%(class)s',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        abstract = True
