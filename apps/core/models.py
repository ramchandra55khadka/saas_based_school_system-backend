from django.db import models
from django.core.exceptions import ValidationError
from apps.tenants.models import Tenant

from utils.abstract_model import AbstractUUID


class AbstractTenantModel(AbstractUUID, models.Model):
    """Abstract base for tenant-scoped models. Provides tenant FK."""
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='%(class)s_records'
    )

    class Meta:
        abstract = True


def ensure_same_tenant(instance, *field_names):
    """Validate that related tenant-scoped objects belong to instance.tenant."""
    errors = {}
    tenant = getattr(instance, 'tenant', None)
    if tenant is None:
        return

    for field_name in field_names:
        related = getattr(instance, field_name, None)
        related_tenant = getattr(related, 'tenant', None)
        if related is not None and related_tenant is not None and related_tenant != tenant:
            errors[field_name] = 'Object belongs to a different school.'

    if errors:
        raise ValidationError(errors)
