from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.core.constants import ADMIN_PRINCIPAL_HOD_ROLES
from apps.user_account.constants import RoleChoices
from utils.permissions import get_membership_role, is_super_admin

from .models import StudentPost, TeacherAnnouncement


class IsStudentOnlyPost(BasePermission):
    """Only students can post, all authenticated users can read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return get_membership_role(request.user, getattr(request, 'tenant', None)) == RoleChoices.STUDENT


class IsTeacherOnlyPost(BasePermission):
    """Only teachers can post announcements, students can read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return get_membership_role(request.user, getattr(request, 'tenant', None)) == RoleChoices.TEACHER


class IsAuthorOrSchoolAdmin(BasePermission):
    """Object-level write gate for author-scoped rows.

    Only the author may edit/delete their own student post or teacher
    announcement; admin/principal/HOD (and the platform super admin) moderate.
    Read stays open to everyone the viewset serves.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if is_super_admin(user):
            return True
        role = get_membership_role(user, getattr(request, 'tenant', None))
        if role in ADMIN_PRINCIPAL_HOD_ROLES:
            return True
        if isinstance(obj, StudentPost):
            return obj.student.user_profile.user_account_id == user.id
        if isinstance(obj, TeacherAnnouncement):
            return obj.teacher.staff.user_profile.user_account_id == user.id
        return False
