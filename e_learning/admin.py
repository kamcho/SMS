from django.contrib import admin
from .models import (
    Strand, Substrand, LearningOutcome, SuggestedActivity,
    AssessmentCriterion, Quiz, Question, QuestionImage,
    Option, QuizAttempt, StudentAnswer, Assignment,
)



class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    
class SubstrandInline(admin.TabularInline):
    model = Substrand
    extra = 0


class LearningOutcomeInline(admin.TabularInline):
    model = LearningOutcome
    extra = 0


class SuggestedActivityInline(admin.TabularInline):
    model = SuggestedActivity
    extra = 0


class AssessmentCriterionInline(admin.TabularInline):
    model = AssessmentCriterion
    extra = 0


class QuestionImageInline(admin.TabularInline):
    model = QuestionImage
    extra = 1


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4


class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    readonly_fields = ['question', 'selected_option', 'text_answer',
                       'score_awarded', 'is_graded', 'ai_feedback', 'ai_confidence']

admin.site.register(StudentAnswer)
# admin.site.register(QuizAttempt)
@admin.register(Strand)
class StrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'order', 'is_active']
    list_filter = ['subject', 'is_active']
    search_fields = ['name']
    inlines = [SubstrandInline]


@admin.register(Substrand)
class SubstrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'strand', 'order', 'is_active']
    list_filter = ['strand__subject', 'is_active']
    search_fields = ['name']
    inlines = [LearningOutcomeInline, SuggestedActivityInline, AssessmentCriterionInline]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'status', 'time_limit_minutes',
                    'question_count', 'total_marks', 'created_by', 'created_at']
    list_filter = ['status', 'subject', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['total_marks', 'question_count']
    filter_horizontal = ['target_classes', 'questions']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'question_type', 'marks', 'is_active']
    list_filter = ['question_type', 'is_active']
    search_fields = ['question']
    inlines = [OptionInline, QuestionImageInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'attempt_number', 'status',
                    'total_score', 'percentage', 'passed', 'started_at', 'submitted_at']
    list_filter = ['status', 'passed', 'quiz']
    search_fields = ['student__first_name', 'student__last_name']
    readonly_fields = ['total_score', 'total_possible', 'percentage', 'passed',
                       'ai_grading_complete']
    inlines = [StudentAnswerInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'quiz', 'target_class', 'due_date', 'is_active']
    list_filter = ['is_active', 'target_class', 'due_date']
    search_fields = ['title', 'quiz__title']
