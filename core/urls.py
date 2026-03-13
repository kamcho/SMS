from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('teacher/dashboard/', views.TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('guardian/dashboard/', views.guardian_dashboard, name='guardian-dashboard'),
    path('students/', views.StudentsListView.as_view(), name='students-list'),
    path('student/create/', views.create_student, name='create-student'),
    path('student/<int:pk>/', views.StudentDetailView.as_view(), name='student-detail'),
    path('classes/', views.ClassesListView.as_view(), name='classes-list'),
    path('class/<int:pk>/', views.ClassDetailView.as_view(), name='class-detail'),
    path('class/<int:class_id>/analytics/', views.class_exam_analytics, name='class-exam-analytics'),
    path('class/<int:class_id>/subject/<int:subject_id>/exam/<int:exam_id>/analytics/', views.subject_exam_analytics, name='subject-exam-analytics'),
    path('configurations/', views.configurations, name='configurations'),
    path('configurations/academic-year/create/', views.create_academic_year, name='create-academic-year'),
    path('configurations/term/create/', views.create_term, name='create-term'),
    path('configurations/grade/create/', views.create_grade, name='create-grade'),
    path('configurations/class/create/', views.create_class, name='create-class'),
    path('configurations/exam/create/', views.create_exam, name='create-exam'),
    path('configurations/fee-structure/create/', views.create_fee_structure, name='create-fee-structure'),
    path('configurations/exam-mode/<int:exam_mode_id>/update/', views.update_exam_mode, name='update-exam-mode'),
    path('configurations/delete/<str:model_type>/<int:item_id>/', views.delete_item, name='delete-item'),
    path('student/<int:student_id>/report/<int:exam_id>/', views.student_report, name='student-report'),
    path('class/<int:class_id>/bulk-reports/<int:exam_id>/', views.bulk_class_reports, name='bulk-class-reports'),
    path('payments/', views.manage_fee_payments, name='manage-fee-payments'),
    path('payments/process/<int:student_id>/', views.process_payment, name='process-payment'),
    path('attendance/<int:class_id>/', views.mark_attendance, name='mark-attendance'),
    path('attendance/<int:class_id>/<str:date>/', views.attendance_detail, name='attendance-detail'),
    path('attendance/data/', views.get_attendance_data, name='get-attendance-data'),
    path('schools-analytics/', views.schools_analytics, name='schools-analytics'),
    path('discipline/', views.discipline_log, name='discipline-log'),
    path('configurations/academic-year/<int:year_id>/activate/', views.activate_academic_year, name='activate-academic-year'),
    path('configurations/term/<int:term_id>/activate/', views.activate_term, name='activate-term'),
]
