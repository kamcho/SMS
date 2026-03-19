from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import Exam, Subject, ExamSubjectConfiguration


@login_required
@require_http_methods(["GET"])
def get_subjects_for_grade(request, grade):
    """Get all subjects for a specific grade"""
    try:
        subjects = Subject.objects.filter(grade=grade).order_by('name')
        subjects_data = [{'id': subject.id, 'name': subject.name} for subject in subjects]
        return JsonResponse({'subjects': subjects_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def get_available_subjects(request, exam_id, grade):
    """Get available subjects for a specific exam and grade (excluding already configured ones)"""
    try:
        exam = get_object_or_404(Exam, id=exam_id)
        
        # Get all subjects for the grade
        subjects = Subject.objects.filter(grade=grade).order_by('name')
        
        # Get subjects that already have configurations for this exam
        configured_subject_ids = ExamSubjectConfiguration.objects.filter(
            exam_id=exam_id,
            subject__grade=grade
        ).values_list('subject_id', flat=True)
        
        # Exclude already configured subjects
        available_subjects = subjects.exclude(id__in=configured_subject_ids)
        subjects_data = [{'id': subject.id, 'name': subject.name} for subject in available_subjects]
        
        return JsonResponse({'subjects': subjects_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
