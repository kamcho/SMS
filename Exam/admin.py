from django.contrib import admin
from .models import Course, Subject, Exam, ExamSUbjectScore

admin.site.register(Course)
admin.site.register(Subject)
admin.site.register(Exam)
admin.site.register(ExamSUbjectScore)
