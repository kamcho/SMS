from django.contrib import admin
from .models import (
    School, 
    Grade, 
    Class, 
    Student, 
    StudentProfile, 
    AcademicYear, 
    Term, 
    ExamMode, 
    StudentDiscipline, 
    AttendanceSession, 
    StudentAttendance
)

class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'student profile'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('adm_no', 'first_name', 'last_name', 'gender', 'joined_date')
    search_fields = ('first_name', 'last_name', 'adm_no')
    list_filter = ('gender', 'is_boarder')
    inlines = (StudentProfileInline,)

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'grade', 'class_teacher')
    list_filter = ('school', 'grade')
    search_fields = ('name',)

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    search_fields = ('name',)

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('name', 'school')
    list_filter = ('school',)

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_id', 'school', 'fee_balance', 'status')
    list_filter = ('status', 'school', 'class_id')
    search_fields = ('student__first_name', 'student__last_name', 'student__adm_no')

# Register remaining models
admin.site.register(Term)
admin.site.register(AcademicYear)
admin.site.register(ExamMode)
admin.site.register(StudentDiscipline)
admin.site.register(AttendanceSession)
admin.site.register(StudentAttendance)