# tenants/admin.py
from django.contrib import admin
from .models import Tenant

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['tenant_id', 'tenant_name', 'org_code', 'created_at']
    search_fields = ['tenant_name', 'org_code']
    readonly_fields = ['tenant_id', 'created_at']
    list_filter = ['created_at']