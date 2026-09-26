from django.contrib import admin
from .models import (
    Student, StudentDocument, StudentAttendance,
    Exam, ExamResult, StudentPromotion,
)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user_profile', 'school_class', 'section', 'roll_number', 'admission_date', 'tenant']
    list_filter = ['school_class', 'section', 'tenant']
    search_fields = ['user_profile__first_name', 'user_profile__last_name', 'roll_number']


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ['student', 'document_type', 'title', 'created_at']
    list_filter = ['document_type', 'tenant']


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'status', 'section', 'tenant']
    list_filter = ['status', 'date', 'tenant']
    date_hierarchy = 'date'


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'exam_type', 'academic_year', 'start_date', 'end_date', 'tenant']
    list_filter = ['exam_type', 'academic_year', 'tenant']


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'subject', 'marks_obtained', 'max_marks', 'grade']
    list_filter = ['exam', 'subject', 'tenant']


@admin.register(StudentPromotion)
class StudentPromotionAdmin(admin.ModelAdmin):
    list_display = ['student', 'from_class', 'to_class', 'from_academic_year', 'to_academic_year', 'promoted_by']
    list_filter = ['from_academic_year', 'to_academic_year', 'tenant']
