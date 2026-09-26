from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.core.mixins import TenantViewSet
from apps.subscription.entitlements import get_student_limit
from utils.permissions import IsAdminOrHOD, IsAdminOrHODOrTeacher, get_membership_role
from .models import (
    Student, StudentDocument, StudentAttendance,
    Exam, ExamResult, StudentPromotion,
)
from .serializers import (
    StudentSerializer, StudentDocumentSerializer,
    StudentAttendanceSerializer, ExamSerializer,
    ExamResultSerializer, StudentPromotionSerializer,
    StudentOnboardSerializer,
)


class StudentViewSet(TenantViewSet):
    """Student records. Admin/HOD can create (admission), students see own."""
    queryset = Student.objects.select_related(
        'user_profile', 'user_profile__user_account', 'school_class', 'section'
    ).all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    # Admission writes (the regular create form and the single-dialog onboard)
    # are admin/HOD; reads stay open to every member.
    write_actions = ('create', 'update', 'partial_update', 'destroy', 'onboard')

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if get_membership_role(user, self.request.tenant) == 'student':
            return qs.filter(user_profile__user_account=user)
        return qs

    def get_permissions(self):
        if self.action in self.write_actions:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='onboard')
    def onboard(self, request):
        """Create a student plus the user account and profile it needs.

        POST /api/students/profiles/onboard/ takes the account, personal-detail
        and school-record fields flattened into one payload and writes the
        ``UserAccount``, ``UserProfile``, ``TenantMembership`` and ``Student``
        rows in a single transaction - see ``StudentOnboardSerializer``. The
        plan's student limit is enforced before anything is written.
        """
        serializer = StudentOnboardSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'tenant': self.require_tenant()},
        )
        serializer.is_valid(raise_exception=True)
        self.enforce_student_limit()
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def enforce_student_limit(self):
        """Stop admissions at the plan's ``max_students`` (a limit, not a feature)."""
        tenant = self.require_tenant()
        limit = get_student_limit(tenant)
        if limit and Student.objects.filter(tenant=tenant).count() >= limit:
            raise ValidationError({
                "detail": (
                    f"This plan allows a maximum of {limit} students. "
                    "Upgrade the school plan to add more."
                )
            })

    def perform_create(self, serializer):
        self.enforce_student_limit()
        super().perform_create(serializer)


class StudentDocumentViewSet(TenantViewSet):
    """Upload and manage student documents."""
    queryset = StudentDocument.objects.select_related('student').all()
    serializer_class = StudentDocumentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHOD]


class StudentAttendanceViewSet(TenantViewSet):
    """Mark and view student attendance. Teachers and Admin can mark."""
    queryset = StudentAttendance.objects.select_related(
        'student', 'student__user_profile', 'academic_year', 'section'
    ).all()
    serializer_class = StudentAttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if get_membership_role(user, self.request.tenant) == 'student':
            return qs.filter(student__user_profile__user_account=user)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHODOrTeacher()]
        return [IsAuthenticated()]


class ExamViewSet(TenantViewSet):
    """Exam management. Admin/HOD can create and manage exams."""
    queryset = Exam.objects.select_related('academic_year').all()
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHOD()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'], url_path='report-card/(?P<student_id>[^/.]+)')
    def report_card(self, request, pk=None, student_id=None):
        """Generate a report card for a specific student for this exam."""
        exam = self.get_object()
        
        # Verify access
        user = request.user
        if get_membership_role(user, self.request.tenant) == 'student':
            own_profile = getattr(user, 'profile', None)
            own_student = getattr(own_profile, 'student', None) if own_profile else None
            if own_student is None or str(own_student.id) != str(student_id):
                raise PermissionDenied("You can only view your own report card.")

        results = ExamResult.objects.filter(exam=exam, student_id=student_id).select_related(
            'subject', 'student', 'student__user_profile'
        )
        
        if not results.exists():
            return Response({"error": "No results found for this student in this exam."}, status=status.HTTP_404_NOT_FOUND)
            
        student_record = results.first().student
        
        report_data = {
            "exam_name": exam.name,
            "exam_type": exam.get_exam_type_display(),
            "student_name": str(student_record.user_profile),
            "roll_number": student_record.roll_number,
            "class": student_record.school_class.name if student_record.school_class else None,
            "section": student_record.section.name if student_record.section else None,
            "results": [
                {
                    "subject": r.subject.name,
                    "marks_obtained": r.marks_obtained,
                    "max_marks": r.max_marks,
                    "grade": r.grade,
                    "remarks": r.remarks
                } for r in results
            ],
            "total_obtained": sum(r.marks_obtained for r in results),
            "total_max": sum(r.max_marks for r in results)
        }
        
        if report_data["total_max"] > 0:
            percentage = (report_data["total_obtained"] / report_data["total_max"]) * 100
            report_data["percentage"] = round(percentage, 2)
            
        return Response({"status": "success", "data": report_data})


class ExamResultViewSet(TenantViewSet):
    """Exam results. Teachers/Admin enter results, students see own."""
    queryset = ExamResult.objects.select_related(
        'exam', 'student', 'student__user_profile', 'subject'
    ).all()
    serializer_class = ExamResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if get_membership_role(user, self.request.tenant) == 'student':
            return qs.filter(student__user_profile__user_account=user)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrHODOrTeacher()]
        return [IsAuthenticated()]


class StudentPromotionViewSet(TenantViewSet):
    """Promote students between classes. Admin only."""
    queryset = StudentPromotion.objects.select_related(
        'student', 'from_class', 'to_class',
        'from_academic_year', 'to_academic_year', 'promoted_by',
    ).all()
    serializer_class = StudentPromotionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHOD]

    def perform_create(self, serializer):
        serializer.save(promoted_by=self.request.user, tenant=self.request.tenant)
