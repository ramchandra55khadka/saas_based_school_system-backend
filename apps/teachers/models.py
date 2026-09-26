from django.conf import settings
from django.db import models
from apps.core.models import ensure_same_tenant, AbstractTenantModel
from apps.academics.models import Section, Subject
from apps.staff.models import Staff
from utils.abstract_model import AbstractTimeStampedModel

from .constants import TEACHING_MEMBERSHIP_ROLES


class Teacher(AbstractTenantModel, AbstractTimeStampedModel):
    """Teacher-specific employment record linked to the school's ``staff.Staff``.

    Identity/contact fields live on ``user_profile.UserProfile`` and employment
    fields live on ``staff.Staff``. This model only represents that the staff
    member has a teaching record in this school.
    """
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name='teachers',
    )
    teaching_license_number = models.CharField(max_length=100, blank=True)
    primary_subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_teachers',
    )
    class_teacher_section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_teacher_sections',
    )
    max_weekly_periods = models.PositiveIntegerField(null=True, blank=True)
    office_hours = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)

    class Meta:
        ordering = [
            'staff__user_profile__first_name', 'staff__user_profile__last_name',
        ]
        verbose_name = 'Teacher'
        verbose_name_plural = 'Teachers'

    def __str__(self):
        return f'{self.staff.user_profile} ({self.staff.employee_id or "No ID"})'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'staff', 'primary_subject', 'class_teacher_section')
        if (
            self.staff_id
            and self.tenant_id
            and not self.staff.user_profile.user_account.memberships.filter(
                tenant=self.tenant,
                is_active=True,
                role__in=TEACHING_MEMBERSHIP_ROLES,
            ).exists()
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({'staff': 'Staff account must have an active teaching membership in this school.'})


class TeacherAttendance(AbstractTenantModel, AbstractTimeStampedModel):
    """Daily attendance for teachers."""
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('on_leave', 'On Leave'),
    ]

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Teacher Attendance'
        verbose_name_plural = 'Teacher Attendance'
        unique_together = ('teacher', 'date')

    def __str__(self):
        return f'{self.teacher} - {self.date} - {self.status}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'teacher')


class LeaveRequest(AbstractTenantModel, AbstractTimeStampedModel):
    """Leave requests submitted by teachers."""
    LEAVE_TYPES = [
        ('sick', 'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('earned', 'Earned Leave'),
        ('maternity', 'Maternity Leave'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leave_approvals'
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Leave Request'
        verbose_name_plural = 'Leave Requests'

    def __str__(self):
        return f'{self.teacher} - {self.get_leave_type_display()} ({self.status})'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'teacher')
