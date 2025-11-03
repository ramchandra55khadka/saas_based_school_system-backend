from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "super-admin")

class IsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")

class IsAdminOrHod(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ["admin", "hod"])

class IsAdminOrHodUserManagement(BasePermission):
    """
    Object-level permission:
    Admin can manage all users in their org.
    HOD can manage only teacher/student.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == "admin":
            return obj.organization == user.organization
        elif user.role == "hod":
            return obj.organization == user.organization and obj.role in ["teacher", "student"]
        return False




class IsTeacherOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "teacher")


class IsStudentOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "student")



class IsAdminOrSuperAdmin(BasePermission):   #for susbcription views to view subscriptions plan
    """Allows access only to admin and super-admin users."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ["admin", "super-admin"]
        )
