from django.contrib import admin

from .models import Parent, StudentGuardian


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['user_profile', 'occupation', 'emergency_contact', 'tenant']
    list_filter = ['tenant']
    search_fields = ['user_profile__first_name', 'user_profile__last_name']


@admin.register(StudentGuardian)
class StudentGuardianAdmin(admin.ModelAdmin):
    list_display = ['student', 'parent', 'relation', 'is_primary', 'tenant']
    list_filter = ['tenant', 'relation', 'is_primary']
    search_fields = ['student__user_profile__first_name', 'parent__user_profile__first_name']
