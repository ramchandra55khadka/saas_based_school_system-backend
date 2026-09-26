from django.urls import path
from .views import AttendanceReportView, FeeReportView, ExamReportView, DemographicsReportView

urlpatterns = [
    path('attendance/', AttendanceReportView.as_view(), name='report-attendance'),
    path('fees/', FeeReportView.as_view(), name='report-fees'),
    path('exams/', ExamReportView.as_view(), name='report-exams'),
    path('demographics/', DemographicsReportView.as_view(), name='report-demographics'),
]
