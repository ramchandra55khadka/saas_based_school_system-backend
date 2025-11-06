# subscription/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['plan', 'get_plan_display', 'price', 'duration_days', 'max_users', 'created_at']
    list_filter = ['plan', 'price', 'duration_days']
    search_fields = ['plan', 'description']
    readonly_fields = ['created_at']
    ordering = ['price']

    def get_plan_display(self, obj):
        return obj.get_plan_display()
    get_plan_display.short_description = 'Plan Name'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'plan', 'plan_name', 'is_active', 'start_date',
        'end_date', 'days_remaining', 'auto_renew'
    ]
    list_filter = ['is_active', 'plan__plan', 'auto_renew', 'start_date']
    search_fields = ['tenant__tenant_name', 'tenant__org_code']
    readonly_fields = ['start_date', 'end_date', 'created_at', 'updated_at', 'days_remaining']
    raw_id_fields = ['tenant', 'plan']

    def plan_name(self, obj):
        return obj.plan.get_plan_display()
    plan_name.short_description = 'Plan'

    def days_remaining(self, obj):
        return obj.days_remaining
    days_remaining.short_description = 'Days Left'

    def has_add_permission(self, request):
        # Optional: prevent manual creation to avoid conflicts with Stripe
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing/editing, but end_date/start_date auto-managed
        return True