from rest_framework.permissions import IsAuthenticated
from apps.core.mixins import TenantViewSet
from utils.permissions import IsAdminOrHOD, get_membership_role
from .models import (
    AcademicYear, Class, Section, Subject,
    TeacherAssignment, TimetableEntry,
)
from .serializers import (
    AcademicYearSerializer, ClassSerializer, SectionSerializer,
    SubjectSerializer, TeacherAssignmentSerializer, TimetableEntrySerializer,
)


class ReferenceDataViewSet(TenantViewSet):
    """Reference data (years, classes, sections, subjects, assignments).

    Any authenticated member of the tenant may **read** these - teachers need
    them to mark attendance and enter results, students need them to label
    their timetable. Writes stay restricted to admin/HOD.
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]


class AcademicYearViewSet(ReferenceDataViewSet):
    """CRUD for academic years. Admin/HOD can manage, everyone can read."""
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


class ClassViewSet(ReferenceDataViewSet):
    """CRUD for classes/grades. Admin/HOD can manage, everyone can read."""
    queryset = Class.objects.all()
    serializer_class = ClassSerializer


class SectionViewSet(ReferenceDataViewSet):
    """CRUD for sections within classes. Admin/HOD can manage, everyone can read."""
    queryset = Section.objects.all()
    serializer_class = SectionSerializer


class SubjectViewSet(ReferenceDataViewSet):
    """CRUD for subjects. Admin/HOD can manage, everyone can read."""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class TeacherAssignmentViewSet(ReferenceDataViewSet):
    """CRUD for teacher-subject-section assignments. Admin/HOD can manage."""
    queryset = TeacherAssignment.objects.select_related(
        'teacher', 'subject', 'section', 'academic_year'
    ).all()
    serializer_class = TeacherAssignmentSerializer


class TimetableEntryViewSet(TenantViewSet):
    """CRUD for timetable entries.

    Admin/HOD manage every entry. Teachers see only the periods they teach,
    students see only their own section's periods. Parents are denied until a
    parent/student link exists (previously they received the tenant-wide read).
    """
    queryset = TimetableEntry.objects.select_related(
        'section', 'subject', 'teacher', 'academic_year'
    ).all()
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = get_membership_role(user, self.request.tenant)
        if role == 'student':
            # Student.section uses related_name='profile_students'
            return qs.filter(
                section__profile_students__user_profile__user_account=user
            ).distinct()
        if role == 'teacher':
            return qs.filter(teacher=user)
        if role == 'parent':
            # No parent->student link exists yet; deny the tenant-wide read
            # instead of exposing every section's timetable to any parent.
            return qs.none()
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]
