from django.urls import path
from .views import CourseListCreateView, SubjectListCreateView, StudentRecordListCreateView

urlpatterns = [
    path("courses/", CourseListCreateView.as_view(), name="course_list_create"),
    path("subjects/", SubjectListCreateView.as_view(), name="subject_list_create"),
    path("student-records/", StudentRecordListCreateView.as_view(), name="student_record_list_create"),
]
