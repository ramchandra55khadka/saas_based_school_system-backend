# academics/admin.py
from django.contrib import admin
from .models import Course, Subject, StudentRecord

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'tenant', 'created_by']
    search_fields = ['name', 'code', 'tenant__tenant_name']
    list_filter = ['tenant']
    readonly_fields = ['created_at']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'teacher', 'tenant']
    search_fields = ['name', 'course__name', 'tenant__tenant_name']
    list_filter = ['tenant']

@admin.register(StudentRecord)
class StudentRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'grade', 'tenant']
    search_fields = ['student__email', 'course__name', 'tenant__tenant_name']
    list_filter = ['tenant', 'grade']