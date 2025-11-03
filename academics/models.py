from django.db import models
from django.conf import settings
from accounts.models import Organization
from accounts.models import User

User = settings.AUTH_USER_MODEL


class Course(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='courses')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_courses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.organization.org_name})"


class Subject(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='subjects')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subjects')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.course.name}"


class StudentRecord(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='student_records')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    grade = models.CharField(max_length=2, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.course.name}"
