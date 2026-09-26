from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user_account', 'first_name', 'last_name', 'phone']
    search_fields = ['user_account__username', 'first_name', 'last_name', 'phone']

