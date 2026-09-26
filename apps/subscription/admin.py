from django.contrib import admin
from .models import Feature, Plan, Subscription

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('key', 'name')

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'max_students', 'feature_count', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    filter_horizontal = ('features',)

    def feature_count(self, obj):
        return obj.features.count()
    feature_count.short_description = 'features'

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'plan', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'plan')
    search_fields = ('tenant__tenant_name',)
    readonly_fields = ('start_date',)