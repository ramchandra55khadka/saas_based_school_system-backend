# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, TenantMembership

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['id', 'email', 'first_name', 'last_name', 'role', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    list_filter = ['role', 'is_active', 'date_joined']
    readonly_fields = ['id', 'date_joined']

@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant', 'role', 'is_active']
    search_fields = ['user__email', 'tenant__tenant_name']
    list_filter = ['role', 'is_active', 'tenant']