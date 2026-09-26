from django.contrib import admin
from .models import (
    AcademicYear, Class, Section, Subject,
    TeacherAssignment, TimetableEntry,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'tenant']
    search_fields = ['name']


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'numeric_name', 'tenant']
    list_filter = ['tenant']
    search_fields = ['name']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'school_class', 'tenant']
    list_filter = ['school_class__name', 'tenant']
    search_fields = ['name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'credit_hours', 'is_optional', 'tenant']
    list_filter = ['is_optional', 'tenant']
    search_fields = ['name', 'code']


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'section', 'academic_year', 'tenant']
    list_filter = ['academic_year', 'tenant']
    search_fields = ['teacher__username', 'subject__name']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ['section', 'day_of_week', 'period_number', 'subject', 'teacher', 'start_time', 'end_time']
    list_filter = ['day_of_week', 'academic_year', 'tenant']
    search_fields = ['subject__name', 'teacher__username']