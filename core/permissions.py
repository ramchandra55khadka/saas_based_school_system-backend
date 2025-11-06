# tenants/permissions.py
from rest_framework.permissions import BasePermission
from accounts.models import TenantMembership

# -----------------------------
# Role-based permissions
# -----------------------------

class IsSuperAdmin(BasePermission):
    """Global super-admin (no tenant required)"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_super_admin())

class IsTenantAdmin(BasePermission):
    """Tenant admin only"""
    def has_permission(self, request, view):
        membership = TenantMembership.objects.filter(user=request.user, is_active=True, role="admin").first()
        return bool(request.user and request.user.is_authenticated and membership)

class IsHOD(BasePermission):
    """Tenant HOD only"""
    def has_permission(self, request, view):
        membership = TenantMembership.objects.filter(user=request.user, is_active=True, role="hod").first()
        return bool(request.user and request.user.is_authenticated and membership)

class IsTeacher(BasePermission):
    """Tenant teacher only"""
    def has_permission(self, request, view):
        membership = TenantMembership.objects.filter(user=request.user, is_active=True, role="teacher").first()
        return bool(request.user and request.user.is_authenticated and membership)

class IsStudent(BasePermission):
    """Tenant student only"""
    def has_permission(self, request, view):
        membership = TenantMembership.objects.filter(user=request.user, is_active=True, role="student").first()
        return bool(request.user and request.user.is_authenticated and membership)

# -----------------------------
# Combined role permissions
# -----------------------------

class IsAdminOrHOD(BasePermission):
    """Tenant admin or HOD"""
    def has_permission(self, request, view):
        membership = TenantMembership.objects.filter(user=request.user, is_active=True).first()
        return bool(request.user and request.user.is_authenticated and membership and request.user.role in ["admin", "hod"])

class IsAdminOrSuperAdmin(BasePermission):
    """Admin or super-admin (for subscription or global views)"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ["admin", "super-admin"])

# -----------------------------
# Object-level permission
# -----------------------------

class IsAdminOrHodUserManagement(BasePermission):
    """
    Object-level permission for managing users within a tenant:
    - Admin: can manage all users in the tenant.
    - HOD: can manage only teacher/student in the tenant.
    """
    def has_object_permission(self, request, view, obj):
        user_membership = TenantMembership.objects.filter(user=request.user, is_active=True).first()
        if not user_membership:
            return False
        
        obj_tenant_ids = [m.tenant.tenant_id for m in obj.memberships.all() if m.is_active]
        user_tenant_id = user_membership.tenant.tenant_id

        if request.user.role == "admin":
            return user_tenant_id in obj_tenant_ids
        elif request.user.role == "hod":
            return user_tenant_id in obj_tenant_ids and obj.role in ["teacher", "student"]
        return False
