import uuid # for generating unique tenant IDs
from django.db import models
from django.utils import timezone

class Tenant(models.Model):
    """
    Represents a tenant (organization) in the multi-tenant architecture.
    Each tenant has a unique identifier and associated metadata.
    """
    tenant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # unique tetant(organization) ID
    tenant_name = models.CharField(max_length=255, unique=True) #organization name
    org_code=models.CharField(max_length=100,unique=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.tenant_name