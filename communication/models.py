from django.db import models
from django.conf import settings
from accounts.models import Organization

User = settings.AUTH_USER_MODEL


class StudentPost(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="student_posts")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_posts")
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Post by {self.student.username} - {self.title}"


class TeacherAnnouncement(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="teacher_announcements")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teacher_announcements")
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Announcement by {self.teacher.username} - {self.title}"
