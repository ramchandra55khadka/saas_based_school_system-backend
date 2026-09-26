from django.contrib import admin
from .models import Department, SchoolSettings, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['tenant_name', 'org_code', 'email', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['tenant_name', 'org_code']
    readonly_fields = ['tenant_id', 'created_at']


@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'grading_system', 'attendance_type', 'timezone']
    list_filter = ['grading_system', 'attendance_type']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'level', 'is_active']
    list_filter = ['tenant', 'level', 'is_active']
    search_fields = ['name', 'tenant__tenant_name']
