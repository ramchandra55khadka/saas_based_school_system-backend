from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import TenantMembership, UserAccount


@admin.register(UserAccount)
class UserAccountAdmin(BaseUserAdmin):
    # ``BaseUserAdmin``'s default fieldsets reference ``first_name`` /
    # ``last_name``, which UserAccount no longer has — define our own.
    list_display = [
        'username', 'email', 'is_active',
        'email_is_verified', 'phone_is_verified', 'is_staff', 'is_superuser',
    ]
    list_filter = [
        'is_active', 'email_is_verified', 'phone_is_verified',
        'is_staff', 'is_superuser',
    ]
    search_fields = ['username', 'email']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Account info', {'fields': ('email',)}),
        ('Verification', {'fields': ('email_is_verified', 'phone_is_verified')}),
        (
            'Permissions',
            {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')},
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'email', 'password1', 'password2'),
            },
        ),
    )


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active']
    search_fields = ['user__username', 'tenant__tenant_name']
