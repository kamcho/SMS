import json
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Student, Class, Grade
from .models import (
    Quiz, Question, Option, QuestionImage, QuizAttempt, StudentAnswer,
    Strand, Substrand, Assignment, AssignmentAttempt, AssignmentAnswer
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  TEACHER / ADMIN  —  Quiz Management
# ──────────────────────────────────────────────

@login_required
def quiz_list(request):
    """List all quizzes — teachers see their own, admins see all."""
    from django.db.models import Avg, Count, Sum, Q, F
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    if request.user.role in ('Admin',) or request.user.is_superuser:
        quizzes = Quiz.objects.all().select_related('subject', 'created_by')
    else:
        quizzes = Quiz.objects.filter(created_by=request.user).select_related('subject', 'created_by')

    # ── Core Stats ───────────────────────────────────────
    total_quizzes = quizzes.count()
    published_quizzes = quizzes.filter(status='published').count()
    draft_quizzes = quizzes.filter(status='draft').count()
    closed_quizzes = quizzes.filter(status='closed').count()

    all_attempts = QuizAttempt.objects.filter(quiz__in=quizzes).exclude(status='in_progress')
    total_attempts = all_attempts.count()
    overall_avg = all_attempts.aggregate(avg=Avg('percentage'))['avg'] or 0
    pass_count = all_attempts.filter(passed=True).count()
    pass_rate = (pass_count / total_attempts * 100) if total_attempts else 0

    # ── Recent Attempts ──────────────────────────────────
    recent_attempts = all_attempts.select_related(
        'student', 'quiz', 'quiz__subject'
    ).order_by('-submitted_at')[:8]

    # ── Subject Performance ──────────────────────────────
    subject_stats = quizzes.filter(status='published').values(
        'subject__name'
    ).annotate(
        avg_score=Avg('attempts__percentage'),
        attempt_count=Count('attempts', filter=Q(attempts__status__in=['submitted', 'graded'])),
        quiz_count=Count('id', distinct=True),
    ).order_by('-avg_score')[:6]

    # ── Weekly Submission Trend (last 4 weeks) ───────────
    four_weeks_ago = timezone.now() - timedelta(weeks=4)
    daily_submissions = (
        all_attempts
        .filter(submitted_at__gte=four_weeks_ago)
        .annotate(day=TruncDate('submitted_at'))
        .values('day')
        .annotate(count=Count('id'), avg_pct=Avg('percentage'))
        .order_by('day')
    )
    trend_labels = [entry['day'].strftime('%d %b') for entry in daily_submissions]
    trend_counts = [entry['count'] for entry in daily_submissions]
    trend_avg    = [round(float(entry['avg_pct'] or 0), 1) for entry in daily_submissions]

    # ── Top Performers ───────────────────────────────────
    top_performers = (
        all_attempts
        .values('student__id', 'student__first_name', 'student__last_name')
        .annotate(avg_pct=Avg('percentage'), attempts_count=Count('id'))
        .order_by('-avg_pct')[:5]
    )

    # ── Grade Distribution ───────────────────────────────
    grade_a = all_attempts.filter(percentage__gte=80).count()
    grade_b = all_attempts.filter(percentage__gte=60, percentage__lt=80).count()
    grade_c = all_attempts.filter(percentage__gte=40, percentage__lt=60).count()
    grade_d = all_attempts.filter(percentage__lt=40).count()

    return render(request, 'e_learning/quiz_list.html', {
        'quizzes': quizzes,
        'total_quizzes': total_quizzes,
        'published_quizzes': published_quizzes,
        'draft_quizzes': draft_quizzes,
        'closed_quizzes': closed_quizzes,
        'total_attempts': total_attempts,
        'overall_avg': overall_avg,
        'pass_rate': pass_rate,
        'recent_attempts': recent_attempts,
        'subject_stats': subject_stats,
        'trend_labels': trend_labels,
        'trend_counts': trend_counts,
        'trend_avg': trend_avg,
        'top_performers': top_performers,
        'grade_a': grade_a,
        'grade_b': grade_b,
        'grade_c': grade_c,
        'grade_d': grade_d,
    })


@login_required
def assignment_create(request):
    """View to assign a quiz to multiple classes or create a custom assignment."""
    from .models import Assignment
    from Exam.models import Subject
    
    # Get quizzes created by teacher (or all for admin)
    if request.user.is_superuser:
        quizzes = Quiz.objects.filter(status='published')
    else:
        quizzes = Quiz.objects.filter(status='published', created_by=request.user)
    
    classes = Class.objects.select_related('grade', 'school').all()
    all_subjects = Subject.objects.all()

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        subject_id = request.POST.get('subject')
        quiz_id = request.POST.get('quiz')
        class_ids = request.POST.getlist('target_class')
        due_date = request.POST.get('due_date')
        
        # New fields
        time_limit = request.POST.get('time_limit_minutes', 0)
        max_attempts = request.POST.get('max_attempts', 1)
        pass_percentage = request.POST.get('pass_percentage', 50)
        shuffle = request.POST.get('shuffle_questions') == 'on'
        available_from = request.POST.get('available_from')
        available_until = request.POST.get('available_until')

        if not title or not class_ids:
            messages.error(request, "Please provide a title and select at least one class.")
            return redirect('e_learning:assignment_create')

        assignment = Assignment.objects.create(
            title=title,
            description=description,
            subject_id=subject_id if subject_id else None,
            quiz_id=quiz_id if quiz_id else None,
            due_date=due_date if due_date else None,
            available_from=available_from if available_from else None,
            available_until=available_until if available_until else None,
            time_limit_minutes=int(time_limit),
            max_attempts=int(max_attempts),
            pass_percentage=int(pass_percentage),
            shuffle_questions=shuffle,
            created_by=request.user,
            is_active=True
        )
        
        if class_ids:
            assignment.target_class.set(class_ids)
            
        messages.success(request, f"Assignment '{title}' created successfully! Now add questions.")
        return redirect('e_learning:assignment_manage', assignment_id=assignment.id)

    return render(request, 'e_learning/assignment_create.html', {
        'quizzes': quizzes,
        'classes': classes,
        'subjects': all_subjects
    })


@login_required
def assignment_manage(request, assignment_id):
    """Manage a specific assignment: add/remove questions, edit metadata."""
    from .models import Assignment, Question, Option, QuestionImage
    from Exam.models import Subject
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Check permission (owner or admin)
    if not request.user.is_superuser and assignment.created_by != request.user:
        messages.error(request, "Permission denied.")
        return redirect('e_learning:quiz_list')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_questions':
            q_ids = request.POST.getlist('questions')
            assignment.questions.add(*q_ids)
            messages.success(request, "Questions added to assignment.")
            
        elif action == 'remove_question':
            q_id = request.POST.get('question_id')
            assignment.questions.remove(q_id)
            messages.success(request, "Question removed from assignment.")

        elif action == 'create_question':
            q_text = request.POST.get('question_text')
            q_type = request.POST.get('question_type')
            marks = request.POST.get('marks', 1)
            expected_answer = request.POST.get('expected_answer', '')

            # Create the question
            new_q = Question.objects.create(
                question=q_text,
                question_type=q_type,
                marks=marks,
                expected_answer=expected_answer,
                is_active=True
            )
            
            # Handle MCQ options
            if q_type == 'multiple_choice':
                options = request.POST.getlist('option_text')
                correct_indices = request.POST.getlist('is_correct')
                for i, opt_text in enumerate(options):
                    if opt_text.strip():
                        Option.objects.create(
                            question=new_q,
                            option=opt_text,
                            is_correct=str(i) in correct_indices,
                            order=i
                        )
            
            # Handle Images
            images = request.FILES.getlist('images')
            for i, img in enumerate(images):
                QuestionImage.objects.create(question=new_q, image=img, order=i)

            # Link to assignment
            assignment.questions.add(new_q)
            messages.success(request, "New question created and added to assignment.")
            
        elif action == 'update_settings':
            assignment.title = request.POST.get('title')
            assignment.description = request.POST.get('description', '')
            assignment.due_date = request.POST.get('due_date') or None
            assignment.available_from = request.POST.get('available_from') or None
            assignment.available_until = request.POST.get('available_until') or None
            assignment.time_limit_minutes = int(request.POST.get('time_limit_minutes', 0))
            assignment.max_attempts = int(request.POST.get('max_attempts', 1))
            assignment.pass_percentage = int(request.POST.get('pass_percentage', 50))
            assignment.shuffle_questions = request.POST.get('shuffle_questions') == 'on'
            
            # Update target classes
            class_ids = request.POST.getlist('target_class')
            if class_ids:
                assignment.target_class.set(class_ids)
                
            assignment.save()
            messages.success(request, "Assignment settings updated successfully.")

        return redirect('e_learning:assignment_manage', assignment_id=assignment.id)

    # Fetch available questions not already in the assignment, with prefetching for faster filtering
    available_questions = Question.objects.exclude(
        id__in=assignment.questions.all().values_list('id', flat=True)
    ).select_related('substrand__strand__subject').order_by('-id')[:200]

    all_subjects = Subject.objects.all()
    all_grades = Grade.objects.all()

    return render(request, 'e_learning/assignment_manage.html', {
        'assignment': assignment,
        'available_questions': available_questions,
        'questions': assignment.questions.all(),
        'subjects': all_subjects,
        'grades': all_grades
    })


@login_required
def quiz_create(request):
    """Create a new quiz with metadata settings."""
    from Exam.models import Subject

    subjects = Subject.objects.all()
    classes = Class.objects.all()
    substrands = Substrand.objects.select_related('strand', 'strand__subject').all()

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        subject_id = request.POST.get('subject')
        substrand_id = request.POST.get('substrand') or None
        time_limit = request.POST.get('time_limit_minutes', 30)
        max_attempts = request.POST.get('max_attempts', 1)
        pass_percentage = request.POST.get('pass_percentage', 50)
        shuffle = request.POST.get('shuffle_questions') == 'on'
        target_class_ids = request.POST.getlist('target_classes')

        quiz = Quiz.objects.create(
            title=title,
            description=description,
            subject_id=subject_id,
            substrand_id=substrand_id,
            created_by=request.user,
            time_limit_minutes=int(time_limit),
            max_attempts=int(max_attempts),
            pass_percentage=int(pass_percentage),
            shuffle_questions=shuffle,
            status='draft',
        )
        if target_class_ids:
            quiz.target_classes.set(target_class_ids)

        messages.success(request, f'Quiz "{quiz.title}" created! Now add questions.')
        return redirect('e_learning:quiz_questions', quiz_id=quiz.pk)

    return render(request, 'e_learning/quiz_create.html', {
        'subjects': subjects,
        'classes': classes,
        'substrands': substrands,
    })


@login_required
def quiz_questions(request, quiz_id):
    """Manage questions for a quiz (using M2M relationship)."""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.prefetch_related('options', 'images').all()

    if request.method == 'POST':
        q_type = request.POST.get('question_type')
        q_text = request.POST.get('question_text')
        q_marks = int(request.POST.get('marks', 1))
        expected = request.POST.get('expected_answer', '')
        images = request.FILES.getlist('images')  # Support multiple images
        order = questions.count()

        # Create the question
        question = Question.objects.create(
            question_type=q_type,
            question=q_text,
            marks=q_marks,
            expected_answer=expected if q_type == 'short_answer' else '',
            order=order,
        )

        # Link it to the quiz
        quiz.questions.add(question)

        # Save images
        for i, img in enumerate(images):
            QuestionImage.objects.create(
                question=question,
                image=img,
                order=i,
            )

        # Save options for multiple choice
        if q_type == 'multiple_choice':
            option_texts = request.POST.getlist('option_text')
            correct_indices = request.POST.getlist('is_correct')
            for i, opt_text in enumerate(option_texts):
                if opt_text.strip():
                    Option.objects.create(
                        question=question,
                        option=opt_text.strip(),
                        is_correct=(str(i) in correct_indices),
                        order=i,
                    )

        messages.success(request, 'Question added successfully!')
        return redirect('e_learning:quiz_questions', quiz_id=quiz.pk)

    from Exam.models import Subject
    # Get all subjects to populate the filter dropdowns
    all_subjects = Subject.objects.all().order_by('grade', 'name')

    return render(request, 'e_learning/quiz_questions.html', {
        'quiz': quiz,
        'questions': questions,
        'all_subjects': all_subjects
    })


@login_required
def search_questions(request):
    """AJAX endpoint: search existing questions not yet in a given quiz."""
    quiz_id = request.GET.get('quiz_id')
    query = request.GET.get('q', '').strip()
    q_type = request.GET.get('type', '')
    grade = request.GET.get('grade', '')
    subject_id = request.GET.get('subject', '')

    quiz = get_object_or_404(Quiz, pk=quiz_id)
    existing_ids = quiz.questions.values_list('id', flat=True)

    qs = Question.objects.filter(is_active=True).exclude(id__in=existing_ids)

    # Filter by Grade/Subject. Note: Questions belong to quizzes, and quizzes belong to subjects.
    # Alternatively they belong to substrands. We'll check the quiz subject.
    if subject_id:
        qs = qs.filter(quizzes__subject_id=subject_id).distinct()
    elif grade:
        qs = qs.filter(quizzes__subject__grade=grade).distinct()

    if query:
        qs = qs.filter(question__icontains=query)
    if q_type:
        qs = qs.filter(question_type=q_type)

    qs = qs.order_by('-created_at')[:20]

    results = []
    for q in qs:
        quizzes_using = list(q.quizzes.values_list('title', flat=True)[:3])
        results.append({
            'id': q.id,
            'question': q.question[:120],
            'question_type': q.get_question_type_display(),
            'type_key': q.question_type,
            'marks': q.marks,
            'used_in': quizzes_using,
            'options_count': q.options.count() if q.question_type == 'multiple_choice' else 0,
        })

    return JsonResponse({'results': results})


@login_required
@require_POST
def add_existing_question(request, quiz_id):
    """Link an existing question to this quiz via M2M."""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question_id = request.POST.get('question_id')
    question = get_object_or_404(Question, pk=question_id)

    if quiz.questions.filter(pk=question.pk).exists():
        messages.warning(request, 'This question is already in the quiz.')
    else:
        quiz.questions.add(question)
        messages.success(request, f'Question added to "{quiz.title}"!')

    return redirect('e_learning:quiz_questions', quiz_id=quiz.pk)


@login_required
def quiz_publish(request, quiz_id):
    """Update quiz status."""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    action = request.POST.get('action', 'publish')
    if action == 'publish':
        if quiz.questions.count() == 0:
            messages.error(request, 'Cannot publish a quiz with no questions.')
        else:
            quiz.status = 'published'
            quiz.available_from = timezone.now()
            quiz.save()
            messages.success(request, f'Quiz "{quiz.title}" is now published!')
    elif action == 'close':
        quiz.status = 'closed'
        quiz.save()
        messages.info(request, f'Quiz "{quiz.title}" has been closed.')
    elif action == 'draft':
        quiz.status = 'draft'
        quiz.save()
        messages.info(request, f'Quiz "{quiz.title}" has been set back to Draft.')

    # Redirect back to where user came from, or quiz_list
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('e_learning:quiz_list')


@login_required
def quiz_results(request, quiz_id):
    """View student attempts for a quiz."""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    attempts = quiz.attempts.select_related('student').order_by('-submitted_at')
    return render(request, 'e_learning/quiz_results.html', {
        'quiz': quiz,
        'attempts': attempts,
    })


@login_required
def attempt_detail(request, attempt_id):
    """Detailed view of a single quiz attempt."""
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz', 'student'), pk=attempt_id)
    answers = attempt.answers.select_related('question').order_by('question__order')
    return render(request, 'e_learning/attempt_detail.html', {
        'attempt': attempt,
        'answers': answers,
    })


@login_required
def delete_question(request, question_id):
    """Unlink/delete a question (for now, unlinking is safer if shared)."""
    question = get_object_or_404(Question, pk=question_id)
    # Since we use M2M, you might want to remove it from the quiz specifically
    quiz_id = request.GET.get('quiz_id')
    if quiz_id:
        quiz = get_object_or_404(Quiz, pk=quiz_id)
        quiz.questions.remove(question)
        if question.quizzes.count() == 0:
            question.delete()
        messages.success(request, 'Question removed from quiz.')
    else:
        question.delete()
        messages.success(request, 'Question deleted permanently.')
    return redirect('e_learning:quiz_questions', quiz_id=quiz_id)


@login_required
def edit_question(request, question_id):
    """Edit an existing question (GET returns JSON data, POST updates)."""
    question = get_object_or_404(Question, pk=question_id)
    
    if request.method == 'GET':
        options = []
        for opt in question.options.all().order_by('order'):
            options.append({
                'id': opt.id,
                'option': opt.option,
                'is_correct': opt.is_correct
            })
        
        data = {
            'id': question.id,
            'question_type': question.question_type,
            'question_text': question.question,
            'marks': question.marks,
            'expected_answer': question.expected_answer,
            'options': options,
        }
        return JsonResponse(data)

    if request.method == 'POST':
        q_type = request.POST.get('question_type')
        q_text = request.POST.get('question_text')
        q_marks = int(request.POST.get('marks', 1))
        expected = request.POST.get('expected_answer', '')
        
        # Update core fields
        question.question_type = q_type
        question.question = q_text
        question.marks = q_marks
        question.expected_answer = expected if q_type == 'short_answer' else ''
        question.save()

        # Handle options for MCQs
        if q_type == 'multiple_choice':
            option_texts = request.POST.getlist('option_text')
            correct_indices = request.POST.getlist('is_correct')
            
            # Clear old and create new to keep it simple (or match by ID)
            question.options.all().delete()
            for i, opt_text in enumerate(option_texts):
                if opt_text.strip():
                    Option.objects.create(
                        question=question,
                        option=opt_text.strip(),
                        is_correct=(str(i) in correct_indices),
                        order=i,
                    )
        else:
            # If changed from MC to Short, clear options
            question.options.all().delete()

        # Support adding new images (optional)
        images = request.FILES.getlist('images')
        for i, img in enumerate(images):
            QuestionImage.objects.create(
                question=question,
                image=img,
                order=question.images.count() + i,
            )

        messages.success(request, 'Question updated successfully!')
        # Redirect back to where user came from, or quiz_list
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('e_learning:quiz_questions', quiz_id=request.POST.get('quiz_id'))


# ──────────────────────────────────────────────
#  STUDENT workflow
# ──────────────────────────────────────────────

@login_required
def student_quiz_list(request):
    """List quizzes available to the current logged-in student (via parent account)."""
    student = _get_student(request)
    
    if not student:
        messages.error(request, 'No student profile linked to your account.')
        return redirect('core:dashboard')

    # Get all students for the switcher
    all_students = request.user.students.all()

    # Get filters
    selected_grade_name = request.GET.get('grade')
    subject_id = request.GET.get('subject')
    
    profile = getattr(student, 'studentprofile', None)
    if not profile:
        messages.error(request, f'No profile found for {student.get_full_name()}.')
        return redirect('core:dashboard')

    # Default to student's grade if none selected
    if not selected_grade_name and profile.class_id:
        selected_grade_name = profile.class_id.grade.name

    # Base queryset: Published quizzes
    quizzes = Quiz.objects.filter(status='published')
    
    # Grade filter (Shared across schools)
    if selected_grade_name:
        quizzes = quizzes.filter(
            models.Q(subject__grade=selected_grade_name) |
            models.Q(target_classes__grade__name=selected_grade_name)
        ).distinct()

    # Subject filter
    if subject_id:
        quizzes = quizzes.filter(subject_id=subject_id)

    # Get assignments for this student's class
    from .models import Assignment
    active_assignments = []
    if profile and profile.class_id:
        active_assignments = Assignment.objects.filter(
            target_class=profile.class_id,
            is_active=True,
        ).select_related('quiz', 'quiz__subject')

    quiz_data = []
    for quiz in quizzes:
        attempts = QuizAttempt.objects.filter(quiz=quiz, student=student)
        best = attempts.order_by('-percentage').first()
        can_attempt = quiz.max_attempts == 0 or attempts.count() < quiz.max_attempts
        
        # Check if this quiz is part of an assignment
        assignment = next((a for a in active_assignments if a.quiz_id == quiz.id), None)
        
        quiz_data.append({
            'type': 'quiz',
            'quiz': quiz,
            'assignment': assignment,
            'attempts_count': attempts.count(),
            'best_score': best.percentage if best else None,
            'can_attempt': can_attempt and quiz.is_available,
        })

    # Add standalone assignments (those without a quiz)
    for assignment in active_assignments.filter(quiz__isnull=True):
        attempts = AssignmentAttempt.objects.filter(assignment=assignment, student=student)
        best = attempts.order_by('-percentage').first()
        can_attempt = assignment.max_attempts == 0 or attempts.count() < assignment.max_attempts
        
        quiz_data.append({
            'type': 'assignment',
            'assignment': assignment,
            'quiz': assignment, # poly-morphism for template
            'attempts_count': attempts.count(),
            'best_score': best.percentage if best else None,
            'can_attempt': can_attempt and assignment.is_available,
        })

    # All attempts for the student (for History section)
    quiz_attempts = QuizAttempt.objects.filter(student=student).select_related('quiz', 'quiz__subject')
    ass_attempts = AssignmentAttempt.objects.filter(student=student).select_related('assignment', 'assignment__subject')
    
    # Add a 'type' attribute to each attempt for the template
    for qa in quiz_attempts: qa.attempt_type = 'quiz'
    for aa in ass_attempts: aa.attempt_type = 'assignment'

    import itertools
    all_attempts = sorted(
        itertools.chain(quiz_attempts, ass_attempts),
        key=lambda x: x.submitted_at or x.started_at,
        reverse=True
    )

    # Calculate average score
    avg_score = 0
    if all_attempts:
        avg_score = sum(a.percentage for a in all_attempts) / len(all_attempts)

    # Metadata for filters
    from core.models import Grade
    grades = [choice[0] for choice in Grade.choices]
    
    from Exam.models import Subject
    subjects = Subject.objects.all()
    if selected_grade_name:
        # Filter subjects that match the selected grade name
        subjects = subjects.filter(grade__iexact=selected_grade_name).order_by('name')
    elif profile and profile.class_id:
        # Fallback to student's own grade subjects if no grade selected
        subjects = subjects.filter(grade__iexact=profile.class_id.grade.name).order_by('name')
    else:
        subjects = subjects.order_by('name')

    return render(request, 'e_learning/student_quiz_list.html', {
        'quiz_data': quiz_data,
        'student': student,
        'all_students': all_students,
        'all_attempts': all_attempts,
        'subjects': subjects,
        'grades': grades,
        'selected_subject': subject_id,
        'selected_grade': selected_grade_name,
        'avg_score': avg_score,
    })


@login_required
def take_quiz(request, quiz_id):
    """Take/resume a quiz."""
    student = _get_student(request)
    if not student:
        return redirect('core:dashboard')

    quiz = get_object_or_404(Quiz, pk=quiz_id, status='published')
    if not quiz.is_available:
        return redirect('e_learning:student_quiz_list')

    attempt = QuizAttempt.objects.filter(quiz=quiz, student=student, status='in_progress').first()
    if not attempt:
        existing_count = QuizAttempt.objects.filter(quiz=quiz, student=student).count()
        if quiz.max_attempts > 0 and existing_count >= quiz.max_attempts:
            return redirect('e_learning:student_quiz_list')
        attempt = QuizAttempt.objects.create(quiz=quiz, student=student, attempt_number=existing_count+1)

    if attempt.is_timed_out:
        attempt.status = 'timed_out'
        attempt.submitted_at = timezone.now()
        attempt.save()
        attempt.calculate_score()
        return redirect('e_learning:quiz_result_student', attempt_id=attempt.pk)

    questions = quiz.questions.filter(is_active=True).prefetch_related('options', 'images')
    if quiz.shuffle_questions:
        questions = questions.order_by('?')
    else:
        questions = questions.order_by('order')

    existing_answers = {a.question_id: a for a in attempt.answers.all()}

    return render(request, 'e_learning/take_quiz.html', {
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
        'existing_answers': existing_answers,
        'time_remaining': attempt.time_remaining_seconds,
    })


@login_required
@require_POST
def save_answer(request):
    """Auto-save via AJAX."""
    attempt_id = request.POST.get('attempt_id')
    question_id = request.POST.get('question_id')
    option_id = request.POST.get('option_id')
    text_answer = request.POST.get('text_answer', '')

    attempt = get_object_or_404(QuizAttempt, pk=attempt_id, status='in_progress')
    question = get_object_or_404(Question, pk=question_id)

    answer, _ = StudentAnswer.objects.update_or_create(
        attempt=attempt,
        question=question,
        defaults={
            'selected_option_id': option_id if question.question_type == 'multiple_choice' else None,
            'text_answer': text_answer if question.question_type == 'short_answer' else '',
        }
    )
    if question.question_type == 'multiple_choice':
        answer.is_graded = False
        answer.save()

    return JsonResponse({'status': 'ok', 'saved': True})


@login_required
@require_POST
def submit_quiz(request, attempt_id):
    """Final submission and grading."""
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id, status='in_progress')
    attempt.status = 'submitted'
    attempt.submitted_at = timezone.now()
    attempt.save()

    for answer in attempt.answers.filter(question__question_type='multiple_choice'):
        answer.auto_grade()

    from .views import _grade_short_answers_with_ai  # Circular Import Prevention if any
    _grade_short_answers_with_ai(attempt)

    attempt.calculate_score()
    return redirect('e_learning:quiz_result_student', attempt_id=attempt.pk)


@login_required
def quiz_result_student(request, attempt_id):
    """Student views their score."""
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id)
    # If student didn't get results yet but they are allowed, show them
    answers = attempt.answers.select_related('question').order_by('question__order')
    return render(request, 'e_learning/quiz_result_student.html', {
        'attempt': attempt,
        'answers': answers,
    })


@login_required
def take_assignment(request, assignment_id):
    """Take/resume a standalone assignment."""
    student = _get_student(request)
    if not student:
        return redirect('core:dashboard')

    assignment = get_object_or_404(Assignment, pk=assignment_id, is_active=True)
    if not assignment.is_available:
        return redirect('e_learning:student_quiz_list')

    # Check if student is in target class
    profile = getattr(student, 'studentprofile', None)
    if not profile or not assignment.target_class.filter(id=profile.class_id_id).exists():
        messages.error(request, "You are not eligible for this assignment.")
        return redirect('e_learning:student_quiz_list')

    attempt = AssignmentAttempt.objects.filter(assignment=assignment, student=student, status='in_progress').first()
    if not attempt:
        existing_count = AssignmentAttempt.objects.filter(assignment=assignment, student=student).count()
        if assignment.max_attempts > 0 and existing_count >= assignment.max_attempts: 
            return redirect('e_learning:student_quiz_list')
        attempt = AssignmentAttempt.objects.create(assignment=assignment, student=student, attempt_number=existing_count+1)

    if attempt.is_timed_out:
        attempt.status = 'timed_out'
        attempt.submitted_at = timezone.now()
        attempt.save()
        attempt.calculate_score()
        return redirect('e_learning:assignment_result_student', attempt_id=attempt.pk)

    questions = assignment.questions.filter(is_active=True).prefetch_related('options', 'images')
    if assignment.shuffle_questions:
        questions = questions.order_by('?')
    else:
        questions = questions.order_by('order')

    existing_answers = {a.question_id: a for a in attempt.answers.all()}

    return render(request, 'e_learning/take_assignment.html', {
        'assignment': assignment,
        'attempt': attempt,
        'questions': questions,
        'existing_answers': existing_answers,
        'time_remaining': attempt.time_remaining_seconds,
    })


@login_required
@require_POST
def save_assignment_answer(request):
    """Auto-save assignment answer via AJAX."""
    attempt_id = request.POST.get('attempt_id')
    question_id = request.POST.get('question_id')
    option_id = request.POST.get('option_id')
    text_answer = request.POST.get('text_answer', '')

    attempt = get_object_or_404(AssignmentAttempt, pk=attempt_id, status='in_progress')
    question = get_object_or_404(Question, pk=question_id)

    answer, _ = AssignmentAnswer.objects.update_or_create(
        attempt=attempt,
        question=question,
        defaults={
            'selected_option_id': option_id if question.question_type == 'multiple_choice' else None,
            'text_answer': text_answer if question.question_type == 'short_answer' else '',
        }
    )
    if question.question_type == 'multiple_choice':
        answer.is_graded = False
        answer.save()

    return JsonResponse({'status': 'ok', 'saved': True})


@login_required
@require_POST
def submit_assignment(request, attempt_id):
    """Final submission and grading for assignment."""
    attempt = get_object_or_404(AssignmentAttempt, pk=attempt_id, status='in_progress')
    attempt.status = 'submitted'
    attempt.submitted_at = timezone.now()
    attempt.save()

    for answer in attempt.answers.filter(question__question_type='multiple_choice'):
        answer.auto_grade()

    _grade_short_answers_with_ai(attempt)

    attempt.calculate_score()
    return redirect('e_learning:assignment_result_student', attempt_id=attempt.pk)


@login_required
def assignment_result_student(request, attempt_id):
    """Student views their assignment score."""
    attempt = get_object_or_404(AssignmentAttempt, pk=attempt_id)
    answers = attempt.answers.select_related('question').order_by('question__order')
    return render(request, 'e_learning/assignment_result_student.html', {
        'attempt': attempt,
        'answers': answers,
    })


def _get_student(request):
    """Helper: get Student linked to current user, supporting session-based student selection."""
    user = request.user
    students = user.students.all()
    
    # Priority 1: student_id in GET (for direct links/switching)
    student_id = request.GET.get('student_id')
    
    # Priority 2: student_id in session (for persistence while taking quiz)
    if not student_id:
        student_id = request.session.get('active_student_id')
        
    if student_id:
        try:
            student = students.get(pk=student_id)
            # Update session for persistence
            request.session['active_student_id'] = student_id
            return student
        except (Student.DoesNotExist, ValueError):
            pass

    # Fallback: First linked student
    student = students.first()
    if student:
        request.session['active_student_id'] = student.id
    return student


def _grade_short_answers_with_ai(attempt):
    """Grade all short-answer questions using OpenAI."""
    try:
        import openai
    except ImportError:
        return

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return

    client = openai.OpenAI(api_key=api_key)

    short_answers = attempt.answers.filter(
        question__question_type='short_answer',
        is_graded=False,
    ).select_related('question')

    for answer in short_answers:
        try:
            max_marks = answer.question.marks
            expected = answer.question.expected_answer or ''
            student_text = answer.text_answer or ''

            prompt = (
                f"Question: {answer.question.question}\n"
                f"Model Answer: {expected}\n"
                f"Student Answer: {student_text}\n"
                f"Max marks: {max_marks}\n"
                "Grade from 0 to max marks. JSON only: {'score': X, 'feedback': '...'}"
            )

            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.2,
                max_tokens=300,
            )

            result = json.loads(response.choices[0].message.content.strip('`').replace('json', '').strip())
            answer.score_awarded = Decimal(str(result.get('score', 0)))
            answer.ai_feedback = result.get('feedback', '')
            answer.is_graded = True
            answer.save()
        except:
            pass
