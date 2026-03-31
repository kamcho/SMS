from django.urls import path
from . import views

app_name = 'e_learning'

urlpatterns = [
    # ── Teacher / Admin ──
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quizzes/create/', views.quiz_create, name='quiz_create'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:assignment_id>/manage/', views.assignment_manage, name='assignment_manage'),
    path('quizzes/<int:quiz_id>/questions/', views.quiz_questions, name='quiz_questions'),
    path('quizzes/<int:quiz_id>/publish/', views.quiz_publish, name='quiz_publish'),
    path('quizzes/<int:quiz_id>/results/', views.quiz_results, name='quiz_results'),
    path('quizzes/<int:quiz_id>/add-existing/', views.add_existing_question, name='add_existing_question'),
    path('questions/search/', views.search_questions, name='search_questions'),
    path('questions/<int:question_id>/delete/', views.delete_question, name='delete_question'),
    path('questions/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('attempts/<int:attempt_id>/detail/', views.attempt_detail, name='attempt_detail'),

    # ── Student ──
    path('my-quizzes/', views.student_quiz_list, name='student_quiz_list'),
    path('take/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('save-answer/', views.save_answer, name='save_answer'),
    path('submit/<int:attempt_id>/', views.submit_quiz, name='submit_quiz'),
    path('result/<int:attempt_id>/', views.quiz_result_student, name='quiz_result_student'),
    
    # standalone assignments
    path('assignment/take/<int:assignment_id>/', views.take_assignment, name='take_assignment'),
    path('assignment/save-answer/', views.save_assignment_answer, name='save_assignment_answer'),
    path('assignment/submit/<int:attempt_id>/', views.submit_assignment, name='submit_assignment'),
    path('assignment/result/<int:attempt_id>/', views.assignment_result_student, name='assignment_result_student'),
]
