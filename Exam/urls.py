from django.urls import path
from . import views

app_name = 'Exam'

urlpatterns = [
    path('', views.ExamListView.as_view(), name='exam-list'),
    path('create/', views.CreateExamView.as_view(), name='create-exam'),
    path('manage/<int:exam_id>/', views.ManageExamView.as_view(), name='manage-exam'),
    path('subject-configurations/<str:grade>/', views.SubjectConfigurationView.as_view(), name='subject-configurations'),
    path('subject-configurations/<str:grade>/<int:exam_id>/', views.SubjectConfigurationView.as_view(), name='subject-configurations-with-exam'),
    path('score-entry/<int:class_id>/<int:subject_id>/<int:exam_id>/', views.TeacherScoreEntryView.as_view(), name='score-entry'),
]
