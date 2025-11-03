from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsStudentOnlyPost(BasePermission):
    """Only students can post, all authenticated users can read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return bool(request.user and request.user.role == "student")


class IsTeacherOnlyPost(BasePermission):
    """Only teachers can post announcements, students can read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return bool(request.user and request.user.role == "teacher")
