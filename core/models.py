from django.db import models
from tenants.models import Tenant

class TenantModel(models.Model):
    """
    Abstract base class for tenant-aware models.
    Ensures logical isolation by linking every record to a tenant.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="%(class)s_records"
    )

    class Meta:
        abstract = True
