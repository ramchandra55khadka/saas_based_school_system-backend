import uuid
from django.db import models
from django.utils.text import slugify

from utils.abstract_model import AbstractTimeStampedModel, AbstractUUID

from .constants import DepartmentLevel


class Tenant(AbstractTimeStampedModel, models.Model):
    """Represents a school/organization in the multi-tenant system."""
    tenant_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    tenant_name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    org_code = models.CharField(max_length=100, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    established_year = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['tenant_name']
        verbose_name = 'School'
        verbose_name_plural = 'Schools'

    def __str__(self):
        return self.tenant_name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.tenant_name) or slugify(self.org_code) or 'school'
            slug = base_slug[:120]
            counter = 2
            qs = type(self).objects.all()
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug__iexact=slug).exists():
                suffix = f'-{counter}'
                slug = f'{base_slug[:120 - len(suffix)]}{suffix}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Department(AbstractUUID, AbstractTimeStampedModel, models.Model):
    """Academic or administrative department within a school."""
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='departments'
    )
    name = models.CharField(max_length=100)
    level = models.CharField(
        max_length=30,
        choices=DepartmentLevel.choices,
        default=DepartmentLevel.OTHER,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['level', 'name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f'{self.name} ({self.tenant.tenant_name})'


class SchoolSettings(AbstractUUID, models.Model):
    """Per-school configuration settings."""
    GRADING_CHOICES = [
        ('percentage', 'Percentage'),
        ('gpa', 'GPA'),
        ('letter', 'Letter Grade'),
    ]
    ATTENDANCE_CHOICES = [
        ('daily', 'Daily'),
        ('period', 'Per Period'),
    ]

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name='settings'
    )
    academic_year_format = models.CharField(
        max_length=50, default='YYYY-YYYY',
        help_text='e.g. 2026-2027'
    )
    grading_system = models.CharField(
        max_length=20, choices=GRADING_CHOICES, default='percentage'
    )
    attendance_type = models.CharField(
        max_length=20, choices=ATTENDANCE_CHOICES, default='daily'
    )
    timezone = models.CharField(max_length=50, default='Asia/Kathmandu')

    class Meta:
        verbose_name = 'School Settings'
        verbose_name_plural = 'School Settings'

    def __str__(self):
        return f'Settings for {self.tenant.tenant_name}'
