from django.contrib import admin
from .models import Teacher, TeacherAttendance, LeaveRequest


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = [
        'staff', 'staff_employee_id', 'primary_subject', 'class_teacher_section',
        'staff_qualification', 'staff_date_of_joining', 'tenant',
    ]
    list_filter = ['tenant', 'primary_subject', 'class_teacher_section']
    search_fields = [
        'staff__user_profile__user_account__username',
        'staff__user_profile__first_name',
        'staff__employee_id',
        'teaching_license_number',
    ]

    @admin.display(description='Employee ID', ordering='staff__employee_id')
    def staff_employee_id(self, obj):
        return obj.staff.employee_id

    @admin.display(description='Qualification', ordering='staff__qualification')
    def staff_qualification(self, obj):
        return obj.staff.qualification

    @admin.display(description='Date of Joining', ordering='staff__date_of_joining')
    def staff_date_of_joining(self, obj):
        return obj.staff.date_of_joining


@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'date', 'status', 'check_in_time', 'check_out_time']
    list_filter = ['status', 'date', 'tenant']
    date_hierarchy = 'date'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'leave_type', 'start_date', 'end_date', 'status', 'approved_by']
    list_filter = ['leave_type', 'status', 'tenant']
    search_fields = ['teacher__staff__user_profile__user_account__username', 'reason']
