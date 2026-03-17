from django.contrib import admin
from .models import (
    Course, 
    Subject, 
    MySubject,
    Exam, 
    ExamSubjectConfiguration, 
    ScoreRanking, 
    ExamSubjectPaper, 
    ExamSUbjectScore
)

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'period', 'year', 'term', 'is_running')
    list_filter = ('year', 'term', 'is_running', 'period')
    search_fields = ('name',)

@admin.register(ExamSubjectConfiguration)
class ExamSubjectConfigurationAdmin(admin.ModelAdmin):
    list_display = ('exam', 'subject', 'max_score', 'paper_count')
    list_filter = ('exam', 'subject')

@admin.register(ExamSUbjectScore)
class ExamSUbjectScoreAdmin(admin.ModelAdmin):
    list_display = ('student', 'paper', 'score', 'grade')
    list_filter = ('paper__exam_subject__exam', 'grade')
    search_fields = ('student__first_name', 'student__last_name', 'student__adm_no')

admin.site.register(Course)
admin.site.register(Subject)
admin.site.register(MySubject)
admin.site.register(ScoreRanking)
admin.site.register(ExamSubjectPaper)
