# communication/models.py
from django.conf import settings
from django.db import models
from apps.core.models import AbstractTenantModel  # ✅ import abstract tenant-aware base model
from apps.students.models import Student
from apps.teachers.models import Teacher
from utils.abstract_model import AbstractTimeStampedModel

from .constants import DEFAULT_TARGET_AUDIENCE, TARGET_AUDIENCE_CHOICES

class StudentPost(AbstractTenantModel, AbstractTimeStampedModel):  # ✅ inherits tenant + timestamps
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="student_posts")
    title = models.CharField(max_length=255)
    content = models.TextField()

    class Meta:
        verbose_name = 'Student Post'
        verbose_name_plural = 'Student Posts'

    def __str__(self):
        return f"Post by {self.student.user_profile} - {self.title}"


class TeacherAnnouncement(AbstractTenantModel, AbstractTimeStampedModel):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="teacher_announcements")
    title = models.CharField(max_length=255)
    content = models.TextField()

    class Meta:
        verbose_name = 'Teacher Announcement'
        verbose_name_plural = 'Teacher Announcements'

    def __str__(self):
        return f"Announcement by {self.teacher.staff.user_profile} - {self.title}"

class Announcement(AbstractTenantModel, AbstractTimeStampedModel):
    """Broadcast messages from School Admin to all Students/Teachers."""
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='announcements_sent')
    target_audience = models.CharField(
        max_length=20,
        choices=TARGET_AUDIENCE_CHOICES,
        default=DEFAULT_TARGET_AUDIENCE,
    )
    title = models.CharField(max_length=200)
    content = models.TextField()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'

    def __str__(self):
        return self.title

class Message(AbstractTenantModel, AbstractTimeStampedModel):
    """Direct messaging (Teacher -> Parent, School -> Student)."""
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages_sent')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages_received')
    subject = models.CharField(max_length=200)
    content = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f"{self.sender.username} to {self.recipient.username}: {self.subject}"

class Notification(AbstractTenantModel, AbstractTimeStampedModel):
    """System-generated alerts for users."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"
