from django.conf import settings
from django.db import models
from apps.core.models import ensure_same_tenant, AbstractTenantModel
from utils.abstract_model import AbstractTimeStampedModel


class AcademicYear(AbstractTenantModel, AbstractTimeStampedModel):
    """Academic year/session for the school."""
    name = models.CharField(max_length=50, help_text='e.g. 2026-2027')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Academic Year'
        verbose_name_plural = 'Academic Years'
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f'{self.name} ({self.tenant.tenant_name})'


class Class(AbstractTenantModel, AbstractTimeStampedModel):
    """A class/grade level in the school (e.g. Grade 10)."""
    name = models.CharField(max_length=100, help_text='e.g. Grade 10')
    numeric_name = models.PositiveIntegerField(
        help_text='Numeric representation for ordering (e.g. 10)'
    )

    class Meta:
        ordering = ['numeric_name']
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f'{self.name} ({self.tenant.tenant_name})'


class Section(AbstractTenantModel, AbstractTimeStampedModel):
    """A section within a class (e.g. Grade 10 - Section A)."""
    name = models.CharField(max_length=50, help_text='e.g. A, B, C')
    school_class = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name='sections'
    )

    class Meta:
        ordering = ['school_class', 'name']
        verbose_name = 'Section'
        verbose_name_plural = 'Sections'
        unique_together = ('school_class', 'name')

    def __str__(self):
        return f'{self.school_class.name} - {self.name}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'school_class')


class Subject(AbstractTenantModel, AbstractTimeStampedModel):
    """A subject offered by the school."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    credit_hours = models.PositiveIntegerField(default=0)
    is_optional = models.BooleanField(default=False)
    school_classes = models.ManyToManyField(
        Class, related_name='subjects', blank=True,
        help_text="Classes that offer this subject (a subject spans many grades).",
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f'{self.name} ({self.code})'


class TeacherAssignment(AbstractTenantModel, AbstractTimeStampedModel):
    """Assigns a teacher to a subject in a specific section for an academic year."""
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='teaching_assignments'
    )
    subject = models.ForeignKey( 
        Subject, on_delete=models.CASCADE, related_name='assignments'
    )
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name='teacher_assignments'
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='teacher_assignments'
    )

    class Meta:
        ordering = ['academic_year', 'section']
        verbose_name = 'Teacher Assignment'
        verbose_name_plural = 'Teacher Assignments'
        unique_together = ('teacher', 'subject', 'section', 'academic_year')

    def __str__(self):
        return f'{self.teacher} teaches {self.subject.name} in {self.section}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'subject', 'section', 'academic_year')
        if (
            self.teacher_id
            and self.tenant_id
            and not self.teacher.memberships.filter(
                tenant=self.tenant,
                is_active=True,
                role__in=['teacher', 'hod', 'principal'],
            ).exists()
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({'teacher': 'Teacher must be an active teaching member of this school.'})


class TimetableEntry(AbstractTenantModel, AbstractTimeStampedModel):
    """A single timetable slot for a section."""
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
    ]

    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='timetable_entries'
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES)
    period_number = models.PositiveIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'period_number']
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'
        unique_together = ('section', 'day_of_week', 'period_number', 'academic_year')

    def __str__(self):
        return f'{self.section} | {self.day_of_week} P{self.period_number} - {self.subject.name}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'section', 'subject', 'academic_year')
        if (
            self.teacher_id
            and self.tenant_id
            and not self.teacher.memberships.filter(
                tenant=self.tenant,
                is_active=True,
                role__in=['teacher', 'hod', 'principal'],
            ).exists()
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({'teacher': 'Teacher must be an active teaching member of this school.'})
