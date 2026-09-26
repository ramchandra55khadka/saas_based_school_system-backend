from django.conf import settings
from django.db import models
from apps.core.models import ensure_same_tenant, AbstractTenantModel
from apps.academics.models import AcademicYear, Class, Section, Subject
from apps.user_profile.models import UserProfile
from utils.abstract_model import AbstractTimeStampedModel

from .constants import BLOOD_GROUP_MAX_LENGTH, STUDENT_REQUIRED_ROLE


class Student(AbstractTenantModel, AbstractTimeStampedModel):
    """Student-specific information linked to a common profile.

    Identity (name, phone, address, date of birth) lives on
    ``user_profile.UserProfile``; this model holds only the school-side record:
    the class/section the student sits in and their roll number in it.
    """
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='student',
    )
    school_class = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profile_students',
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profile_students',
    )
    roll_number = models.PositiveIntegerField(null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=BLOOD_GROUP_MAX_LENGTH, blank=True)

    class Meta:
        ordering = ['school_class', 'section', 'roll_number']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'school_class', 'section', 'roll_number'],
                name='unique_student_roll_per_section',
                condition=models.Q(roll_number__isnull=False),
            )
        ]

    def __str__(self):
        return f'{self.user_profile} - {self.roll_number or "No Roll"}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'school_class', 'section')
        if self.section_id and self.school_class_id and self.section.school_class_id != self.school_class_id:
            from django.core.exceptions import ValidationError
            raise ValidationError({'section': 'Section must belong to the selected class.'})
        if (
            self.user_profile_id
            and self.tenant_id
            and not self.user_profile.user_account.memberships.filter(
                tenant=self.tenant,
                is_active=True,
                role=STUDENT_REQUIRED_ROLE,
            ).exists()
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({'user_profile': 'Account must have an active student membership in this school.'})


class StudentDocument(AbstractTenantModel, AbstractTimeStampedModel):
    """Documents uploaded for a student."""
    DOCUMENT_TYPES = [
        ('birth_certificate', 'Birth Certificate'),
        ('transfer_certificate', 'Transfer Certificate'),
        ('marksheet', 'Marksheet'),
        ('photo', 'Photo'),
        ('other', 'Other'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='student_documents/%Y/%m/')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Student Document'
        verbose_name_plural = 'Student Documents'

    def __str__(self):
        return f'{self.student} - {self.get_document_type_display()}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'student')


class StudentAttendance(AbstractTenantModel, AbstractTimeStampedModel):
    """Daily attendance record for a student."""
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE,
        related_name='student_attendance_records'
    )
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE,
        related_name='student_attendance_records'
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Student Attendance'
        verbose_name_plural = 'Student Attendance'
        unique_together = ('student', 'date')

    def __str__(self):
        return f'{self.student} - {self.date} - {self.status}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'student', 'academic_year', 'section')


class Exam(AbstractTenantModel, AbstractTimeStampedModel):
    """An examination event."""
    EXAM_TYPES = [
        ('unit_test', 'Unit Test'),
        ('midterm', 'Midterm'),
        ('final', 'Final'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPES)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE,
        related_name='exams'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Exam'
        verbose_name_plural = 'Exams'

    def __str__(self):
        return f'{self.name} ({self.get_exam_type_display()})'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'academic_year')


class ExamResult(AbstractTenantModel, AbstractTimeStampedModel):
    """Individual student result for a subject in an exam."""
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='results'
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='exam_results'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name='exam_results'
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2)
    grade = models.CharField(max_length=5, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['exam', 'student']
        verbose_name = 'Exam Result'
        verbose_name_plural = 'Exam Results'
        unique_together = ('exam', 'student', 'subject')

    def __str__(self):
        return f'{self.student} - {self.exam.name} - {self.subject.name}: {self.marks_obtained}/{self.max_marks}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'exam', 'student', 'subject')


class StudentPromotion(AbstractTenantModel, AbstractTimeStampedModel):
    """Records a student's promotion from one class to another."""
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='promotions'
    )
    from_class = models.ForeignKey(
        Class, on_delete=models.CASCADE,
        related_name='promotions_from'
    )
    to_class = models.ForeignKey(
        Class, on_delete=models.CASCADE,
        related_name='promotions_to'
    )
    from_academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE,
        related_name='promotions_from'
    )
    to_academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE,
        related_name='promotions_to'
    )
    promoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='promotions_given'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Student Promotion'
        verbose_name_plural = 'Student Promotions'

    def __str__(self):
        return f'{self.student} promoted from {self.from_class} to {self.to_class}'

    def clean(self):
        super().clean()
        ensure_same_tenant(
            self,
            'student',
            'from_class',
            'to_class',
            'from_academic_year',
            'to_academic_year',
        )
