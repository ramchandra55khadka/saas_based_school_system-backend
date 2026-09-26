from django.contrib import admin

from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['user_profile', 'designation', 'employee_id', 'department', 'tenant', 'is_active']
    list_filter = ['tenant', 'designation', 'department', 'is_active']
    search_fields = ['user_profile__first_name', 'user_profile__last_name', 'employee_id']
