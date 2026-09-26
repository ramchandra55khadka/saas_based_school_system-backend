from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.subscription.constants import FeatureKey
from apps.subscription.entitlements import HasFeatureAccess
from utils.permissions import IsReportsViewer
from apps.core.mixins import TenantAPIView
from django.db.models import Sum, Count, Avg
from apps.students.models import StudentAttendance, Student, ExamResult
from apps.teachers.models import TeacherAttendance, Teacher
from apps.finance.models import StudentInvoice

class AttendanceReportView(TenantAPIView):
    feature_key = FeatureKey.REPORTS
    permission_classes = [IsAuthenticated, HasFeatureAccess, IsReportsViewer]

    def get(self, request):
        tenant = self.require_tenant()
        academic_year_id = request.query_params.get('academic_year_id')
        
        if not academic_year_id:
            return Response({"error": "academic_year_id is required"}, status=400)
            
        student_att = StudentAttendance.objects.filter(tenant=tenant, academic_year_id=academic_year_id)
        teacher_att = TeacherAttendance.objects.filter(tenant=tenant)
        
        return Response({
            "students": {
                "total_records": student_att.count(),
                "present": student_att.filter(status='present').count(),
                "absent": student_att.filter(status='absent').count(),
            },
            "teachers": {
                "total_records": teacher_att.count(),
                "present": teacher_att.filter(status='present').count(),
                "absent": teacher_att.filter(status='absent').count(),
            }
        })

class FeeReportView(TenantAPIView):
    feature_key = FeatureKey.REPORTS
    permission_classes = [IsAuthenticated, HasFeatureAccess, IsReportsViewer]

    def get(self, request):
        tenant = self.require_tenant()
        academic_year_id = request.query_params.get('academic_year_id')
        
        if not academic_year_id:
            return Response({"error": "academic_year_id is required"}, status=400)
            
        invoices = StudentInvoice.objects.filter(tenant=tenant, academic_year_id=academic_year_id)
        
        total_billed = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_invoices = invoices.count()
        paid_invoices = invoices.filter(status='paid').count()
        unpaid_invoices = invoices.filter(status='unpaid').count()
        
        # Calculate amount paid manually or we could have a DB field, but let's approximate
        # We can sum payments directly but since it's a simple report we'll just return status counts for now
        
        return Response({
            "total_billed": total_billed,
            "total_invoices": total_invoices,
            "paid_invoices": paid_invoices,
            "unpaid_invoices": unpaid_invoices,
            "partial_invoices": total_invoices - paid_invoices - unpaid_invoices
        })

class ExamReportView(TenantAPIView):
    feature_key = FeatureKey.REPORTS
    permission_classes = [IsAuthenticated, HasFeatureAccess, IsReportsViewer]

    def get(self, request):
        tenant = self.require_tenant()
        exam_id = request.query_params.get('exam_id')
        
        if not exam_id:
            return Response({"error": "exam_id is required"}, status=400)
            
        results = ExamResult.objects.filter(tenant=tenant, exam_id=exam_id)
        
        avg_marks = results.values('subject__name').annotate(
            avg_obtained=Avg('marks_obtained')
        )
        
        return Response({
            "subject_averages": list(avg_marks),
            "total_results": results.count()
        })

class DemographicsReportView(TenantAPIView):
    feature_key = FeatureKey.REPORTS
    permission_classes = [IsAuthenticated, HasFeatureAccess, IsReportsViewer]

    def get(self, request):
        tenant = self.require_tenant()
        
        students = Student.objects.filter(tenant=tenant)
        teachers = Teacher.objects.filter(tenant=tenant)
        
        class_distribution = students.values('school_class__name').annotate(count=Count('id'))
        
        return Response({
            "total_students": students.count(),
            "total_teachers": teachers.count(),
            "class_distribution": list(class_distribution)
        })
