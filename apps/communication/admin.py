from django.contrib import admin
from .models import StudentPost, TeacherAnnouncement, Announcement, Message, Notification

@admin.register(StudentPost)
class StudentPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'tenant', 'created_at')

@admin.register(TeacherAnnouncement)
class TeacherAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'tenant', 'created_at')

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'sender', 'target_audience', 'tenant', 'created_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'recipient', 'is_read', 'tenant', 'created_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'is_read', 'tenant', 'created_at')