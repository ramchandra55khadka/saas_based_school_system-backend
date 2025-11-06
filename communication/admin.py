# communication/admin.py
from django.contrib import admin
from .models import StudentPost, TeacherAnnouncement

@admin.register(StudentPost)
class StudentPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'student', 'tenant', 'created_at']
    search_fields = ['title', 'student__email', 'tenant__tenant_name']
    list_filter = ['tenant', 'created_at']
    readonly_fields = ['created_at']

@admin.register(TeacherAnnouncement)
class TeacherAnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'tenant', 'created_at']
    search_fields = ['title', 'teacher__email', 'tenant__tenant_name']
    list_filter = ['tenant', 'created_at']
    readonly_fields = ['created_at']