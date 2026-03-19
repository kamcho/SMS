from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from core.models import Class, StudentProfile, TeacherClassProfile
from .models import Exam, Subject, ExamSUbjectScore, ExamSubjectConfiguration, ExamSubjectPaper, ScoreRanking
from .forms import ExamForm, ExamSubjectConfigurationForm, ExamSubjectPaperForm, ScoreRankingForm

class TeacherScoreEntryView(LoginRequiredMixin, View):
    def get(self, request, class_id, subject_id, exam_id):
        # 1. Verify access
        class_obj = get_object_or_404(Class, id=class_id)
        if not request.user.is_superuser and request.user != class_obj.invigilator and request.user != class_obj.class_teacher:
            try:
                assignment = TeacherClassProfile.objects.get(
                    user=request.user, 
                    class_id_id=class_id, 
                    subject_id=subject_id
                )
            except TeacherClassProfile.DoesNotExist:
                messages.error(request, "You are not permitted to enter scores for this class subject.")
                return redirect('core:teacher-dashboard')

        subject = get_object_or_404(Subject, id=subject_id)
        exam = get_object_or_404(Exam, id=exam_id)
        # 2. Get subject configuration and papers
        subject_config = ExamSubjectConfiguration.objects.filter(
            exam=exam, 
            subject=subject
        ).first()
        
        papers = []
        if subject_config:
            papers = ExamSubjectPaper.objects.filter(exam_subject=subject_config).order_by('paper_number')
        
        # 3. Get students and existing scores
        students_profiles = StudentProfile.objects.filter(class_id=class_obj).select_related('student')
        existing_scores = ExamSUbjectScore.objects.filter(
            paper__exam_subject__exam=exam, 
            paper__exam_subject__subject=subject, 
            student__studentprofile__class_id=class_obj
        )
        
        # Create scores map: {student_id: {paper_id: score}}
        scores_map = {}
        for score in existing_scores:
            if score.student_id not in scores_map:
                scores_map[score.student_id] = {}
            scores_map[score.student_id][score.paper_id] = score.score

        # 4. Create a combined list
        student_data = []
        for profile in students_profiles.order_by('student__first_name'):
            student_scores = {}
            for paper in papers:
                student_scores[paper.id] = scores_map.get(profile.student.id, {}).get(paper.id, '')
            
            student_data.append({
                'student': profile.student,
                'scores': student_scores,
            })
            
        context = {
            'class_obj': class_obj,
            'subject': subject,
            'exam': exam,
            'papers': papers,
            'student_data': student_data,
            'subject_config': subject_config,
        }
        return render(request, 'Exam/score_entry.html', context)

    def post(self, request, class_id, subject_id, exam_id):
        # 1. Verify access
        class_obj = get_object_or_404(Class, id=class_id)
        if not request.user.is_superuser and request.user != class_obj.invigilator and request.user != class_obj.class_teacher:
            try:
                TeacherClassProfile.objects.get(
                    user=request.user, 
                    class_id_id=class_id, 
                    subject_id=subject_id
                )
            except TeacherClassProfile.DoesNotExist:
                messages.error(request, "Permission denied.")
                return redirect('core:teacher-dashboard')
                
        subject = get_object_or_404(Subject, id=subject_id)
        exam = get_object_or_404(Exam, id=exam_id)
        
        # Get subject configuration and papers
        subject_config = ExamSubjectConfiguration.objects.filter(
            exam=exam, 
            subject=subject
        ).first()
        
        papers = []
        if subject_config:
            papers = ExamSubjectPaper.objects.filter(exam_subject=subject_config)
        
        # 2. Process submitted scores for all papers
        students_profiles = StudentProfile.objects.filter(class_id=class_obj)
        for profile in students_profiles:
            for paper in papers:
                score_input = request.POST.get(f'score_{profile.student.id}_{paper.id}')
                if score_input and score_input.strip() != '':
                    try:
                        score_val = int(score_input)
                        # Validate score is within paper's maximum
                        if score_val <= paper.out_of:
                            # Get or Create the score record
                            score_record, created = ExamSUbjectScore.objects.get_or_create(
                                paper=paper,
                                student=profile.student,
                                defaults={'score': score_val, 'grade': 'BE'}
                            )
                            if not created and score_record.score != score_val:
                                score_record.score = score_val
                                score_record.save()
                    except ValueError:
                        pass
        
        messages.success(request, f"Scores saved successfully for {subject.name} - {exam.name}")
        return redirect('core:teacher-dashboard')


class CreateExamView(LoginRequiredMixin, View):
    def get(self, request):
        # Check permissions - only exam officer can create exams
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to create exams. Only the Exam Officer can perform this action.')
            return redirect('core:dashboard')
        
        form = ExamForm()
        
        context = {
            'form': form,
            'page_title': 'Create New Exam',
            'breadcrumb_title': 'Create Exam',
        }
        
        return render(request, 'Exam/create_exam.html', context)
    
    def post(self, request):
        # Check permissions - only exam officer can create exams
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to create exams. Only the Exam Officer can perform this action.')
            return redirect('core:dashboard')
        
        form = ExamForm(request.POST)
        
        if form.is_valid():
            try:
                # Deactivate all other exams
                Exam.objects.update(is_running=False)
                exam = form.save(commit=False)
                exam.created_by = request.user
                exam.updated_by = request.user
                exam.save()
                messages.success(request, f'Exam "{exam.name}" has been created successfully!')
                return redirect('core:dashboard')
            except Exception as e:
                messages.error(request, f'Error creating exam: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        context = {
            'form': form,
            'page_title': 'Create New Exam',
            'breadcrumb_title': 'Create Exam',
        }
        
        return render(request, 'Exam/create_exam.html', context)


class ManageExamView(LoginRequiredMixin, View):
    def get(self, request, exam_id):
        # Check permissions - only exam officer can manage exams
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to manage exams. Only the Exam Officer can perform this action.')
            return redirect('core:dashboard')
        
        exam = get_object_or_404(Exam, id=exam_id)
        
        # Get subject configurations for this exam, grouped by grade
        subject_configs = ExamSubjectConfiguration.objects.filter(
            exam=exam
        ).select_related('subject').prefetch_related('examsubjectpaper_set').order_by('subject__grade', 'subject__name')
        from core.models import ExamMode
        # Check if exam is active: BOTH is_running AND ExamMode active for this exam
        exam_mode = ExamMode.objects.first()
        exam_is_active = exam.is_running and exam_mode is not None and exam_mode.exam_id == exam.id and exam_mode.active
        
        # Group configurations by grade
        configs_by_grade = {}
        all_grades = set()
        
        for config in subject_configs:
            grade = config.subject.grade
            all_grades.add(grade)
            if grade not in configs_by_grade:
                configs_by_grade[grade] = []
            configs_by_grade[grade].append(config)
        
        # Sort grades
        sorted_grades = sorted(all_grades)
        
        # Get all available subjects grouped by grade
        subjects_by_grade = {}
        subjects = Subject.objects.all().order_by('grade', 'name')
        for subject in subjects:
            if subject.grade not in subjects_by_grade:
                subjects_by_grade[subject.grade] = []
            subjects_by_grade[subject.grade].append(subject)
        
        # Show all grades that have subjects
        if subjects_by_grade:
            sorted_grades = sorted(subjects_by_grade.keys())
        
        context = {
            'exam': exam,
            'exam_form': ExamForm(instance=exam),
            'configs_by_grade': configs_by_grade,
            'sorted_grades': sorted_grades,
            'subjects_by_grade': subjects_by_grade,
            'exam_is_active': exam_is_active,
            'page_title': f'Manage Exam: {exam.name}',
            'breadcrumb_title': 'Manage Exam',
        }
        
        return render(request, 'Exam/manage_exam.html', context)
    
    def post(self, request, exam_id):
        # Check permissions - only exam officer can manage exams
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to manage exams. Only the Exam Officer can perform this action.')
            return redirect('core:dashboard')
        
        exam = get_object_or_404(Exam, id=exam_id)
        
        # Handle exam activation - singleton ExamMode pattern
        if 'activate_exam' in request.POST:
            from core.models import ExamMode
            # 1. Deactivate all other exams' is_running
            Exam.objects.exclude(id=exam.id).update(is_running=False)
            # 2. Set this exam's is_running to True
            exam.is_running = True
            exam.save()
            # 3. Update the singleton ExamMode (get or create the single record)
            exam_mode = ExamMode.objects.first()
            if exam_mode:
                exam_mode.exam = exam
                exam_mode.active = True
                exam_mode.save()
            else:
                ExamMode.objects.create(exam=exam, active=True)
            messages.success(request, f'Exam "{exam.name}" is now active. Teachers can now upload marks.')
            return redirect('Exam:manage-exam', exam_id=exam_id)
        
        # Handle exam deactivation
        if 'deactivate_exam' in request.POST:
            from core.models import ExamMode
            # 1. Set this exam's is_running to False
            exam.is_running = False
            exam.save()
            # 2. Deactivate the singleton ExamMode
            exam_mode = ExamMode.objects.first()
            if exam_mode and exam_mode.exam_id == exam.id:
                exam_mode.active = False
                exam_mode.save()
            messages.success(request, f'Exam "{exam.name}" has been deactivated. Teachers can no longer upload marks.')
            return redirect('Exam:manage-exam', exam_id=exam_id)
        
        # Handle different form actions
        action = request.POST.get('action')
        
        if action == 'update_exam':
            return self._update_exam(request, exam)
        elif action == 'add_subject':
            return self._add_subject_config(request, exam)
        elif action == 'add_paper':
            return self._add_paper_config(request, exam)
        elif action.startswith('delete_'):
            return self._delete_item(request, action)
        
        messages.error(request, 'Invalid action.')
        return redirect('Exam:manage-exam', exam_id=exam_id)
    
    def _update_exam(self, request, exam):
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.updated_by = request.user
            exam.save()
            messages.success(request, f'Exam "{exam.name}" has been updated successfully!')
        else:
            messages.error(request, 'Please correct errors below.')
        
        return redirect('Exam:manage-exam', exam_id=exam.id)
    
    def _add_subject_config(self, request, exam):
        form = ExamSubjectConfigurationForm(request.POST)
        if form.is_valid():
            try:
                config = form.save(commit=False)
                config.exam = exam
                config.save()
                
                messages.success(request, f'Subject configuration added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding subject configuration: {str(e)}')
        else:
            messages.error(request, 'Please correct errors below.')
        
        return redirect('Exam:manage-exam', exam_id=exam.id)
    
    def _add_paper_config(self, request, exam):
        form = ExamSubjectPaperForm(request.POST)
        if form.is_valid():
            try:
                paper = form.save(commit=False)
                # Get the subject config ID from the form
                subject_config_id = request.POST.get('subject_config_id')
                if subject_config_id:
                    subject_config = get_object_or_404(ExamSubjectConfiguration, id=subject_config_id)
                    paper.exam_subject = subject_config
                    paper.save()
                    messages.success(request, f'Paper configuration added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding paper configuration: {str(e)}')
        else:
            messages.error(request, 'Please correct errors below.')
        
        return redirect('Exam:manage-exam', exam_id=exam.id)
    
    def _delete_item(self, request, action):
        try:
            if action == 'delete_subject':
                item_id = request.POST.get('item_id')
                config = get_object_or_404(ExamSubjectConfiguration, id=item_id)
                config.delete()
                messages.success(request, 'Subject configuration deleted successfully!')
            elif action == 'delete_paper':
                item_id = request.POST.get('item_id')
                paper = get_object_or_404(ExamSubjectPaper, id=item_id)
                paper.delete()
                messages.success(request, 'Paper configuration deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting item: {str(e)}')
        
        # Check if this is an AJAX request or form submission
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        else:
            # For regular form submissions, redirect back to the same page
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            else:
                # Fallback redirect
                return redirect('Exam:exam-list')


class ExamListView(LoginRequiredMixin, View):
    def get(self, request):
        # Check permissions - only exam officer can view exams
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to view exams. Only the Exam Officer can access this page.')
            return redirect('core:dashboard')
        
        # Get filter parameters
        selected_year = request.GET.get('year')
        selected_term = request.GET.get('term')
        
        # Start with base queryset
        exams = Exam.objects.select_related('year', 'term').order_by('-id')
        
        # Apply filters only if they have values
        if selected_year and selected_year != '':
            exams = exams.filter(year_id=selected_year)
        if selected_term and selected_term != '':
            exams = exams.filter(term_id=selected_term)
        
        # Get filter options
        from core.models import AcademicYear, Term
        years = AcademicYear.objects.filter(is_active=True).order_by('-start_date')
        terms = Term.objects.filter(is_active=True).order_by('name')
        
        context = {
            'exams': exams,
            'years': years,
            'terms': terms,
            'selected_year': selected_year,
            'selected_term': selected_term,
            'page_title': 'Exams List',
            'breadcrumb_title': 'Exams',
        }
        
        return render(request, 'Exam/exam_list.html', context)


class SubjectConfigurationView(LoginRequiredMixin, View):
    def get(self, request, grade, exam_id=None):
        # Check permissions - only exam officer can manage subject configurations
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to manage subject configurations. Only the Exam Officer can perform this action.')
            return redirect('core:dashboard')
        
        # Get existing subject configurations for subjects in this grade
        subject_configs = ExamSubjectConfiguration.objects.filter(
            subject__grade=grade
        )
        
        if exam_id:
            subject_configs = subject_configs.filter(exam_id=exam_id)
            
        subject_configs = subject_configs.select_related('exam', 'subject').prefetch_related('examsubjectpaper_set').order_by('subject__name')
        
        # Get all subjects for this grade
        subjects = Subject.objects.filter(grade=grade).order_by('name')
        configured_subject_ids = []
        if exam_id:
            configured_subject_ids = list(subject_configs.values_list('subject_id', flat=True))
        
        # Get all exams (since grade field was removed, we'll show all exams)
        exams = Exam.objects.all().order_by('-id')
        
        # Create form with pre-selected exam if exam_id is provided
        subject_config_form = ExamSubjectConfigurationForm(grade=grade, exam_id=exam_id)
        selected_exam = None
        if exam_id:
            try:
                selected_exam = get_object_or_404(Exam, id=exam_id)
                subject_config_form.fields['exam'].initial = selected_exam
                subject_config_form.fields['exam'].queryset = exams
            except:
                pass
        
        context = {
            'grade': grade,
            'subjects': subjects,
            'subject_configs': subject_configs,
            'configured_subject_ids': configured_subject_ids,
            'exams': exams,
            'selected_exam': selected_exam,
            'subject_config_form': subject_config_form,
            'paper_form': ExamSubjectPaperForm(),
            'score_ranking_form': ScoreRankingForm(),
            'exam_id': exam_id,
            'page_title': f'Subject Configurations - Grade {grade}',
            'breadcrumb_title': f'Grade {grade} Subjects',
        }
        
        return render(request, 'Exam/subject_configurations.html', context)
    
    def post(self, request, grade, exam_id=None):
        # Check permissions - only exam officer can manage subject configurations
        if not request.user.is_superuser and not getattr(request.user, 'is_exam_officer', False):
            messages.error(request, 'You do not have permission to manage subject configurations. Only the Exam Officer can perform this action.')
            return redirect('core:dashboard')
        
        # Handle different form actions
        action = request.POST.get('action')
        
        if action == 'add_subject_config':
            return self._add_subject_config(request, grade, exam_id)
        elif action == 'add_paper':
            return self._add_paper_config(request, grade, exam_id)
        elif action == 'add_score_ranking':
            return self._add_score_ranking(request, grade, exam_id)
        elif action.startswith('delete_'):
            return self._delete_item(request, action)
        
        messages.error(request, 'Invalid action.')
        if exam_id:
            return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
        else:
            return redirect('Exam:subject-configurations', grade=grade)
    
    def _add_subject_config(self, request, grade, exam_id=None):
        form = ExamSubjectConfigurationForm(request.POST, grade=grade)
        if form.is_valid():
            try:
                # Get the exam for this configuration
                posted_exam_id = request.POST.get('exam')
                if not posted_exam_id:
                    messages.error(request, 'Please select an exam.')
                    if exam_id:
                        return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
                    else:
                        return redirect('Exam:subject-configurations', grade=grade)
                
                exam = get_object_or_404(Exam, id=posted_exam_id)
                
                # Get the subject and verify it belongs to the correct grade
                subject_id = request.POST.get('subject')
                if not subject_id:
                    messages.error(request, 'Please select a subject.')
                    if exam_id:
                        return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
                    else:
                        return redirect('Exam:subject-configurations', grade=grade)
                
                subject = get_object_or_404(Subject, id=subject_id)
                if subject.grade != grade:
                    messages.error(request, f'This subject does not belong to Grade {grade}.')
                    if exam_id:
                        return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
                    else:
                        return redirect('Exam:subject-configurations', grade=grade)
                
                config = form.save(commit=False)
                config.exam = exam
                config.subject = subject
                config.save()
                
                messages.success(request, f'Subject configuration added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding subject configuration: {str(e)}')
        else:
            # Debug: show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            messages.error(request, 'Please correct errors below.')
        
        if exam_id:
            return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
        else:
            return redirect('Exam:subject-configurations', grade=grade)
    
    def _add_paper_config(self, request, grade, exam_id=None):
        form = ExamSubjectPaperForm(request.POST)
        if form.is_valid():
            try:
                paper = form.save(commit=False)
                # Get the subject config ID from the form
                subject_config_id = request.POST.get('subject_config_id')
                if subject_config_id:
                    subject_config = get_object_or_404(ExamSubjectConfiguration, id=subject_config_id)
                    # Verify this config belongs to the correct grade
                    if subject_config.subject.grade != grade:
                        messages.error(request, 'Invalid subject configuration.')
                        if exam_id:
                            return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
                        else:
                            return redirect('Exam:subject-configurations', grade=grade)
                    paper.exam_subject = subject_config
                    paper.save()
                    messages.success(request, f'Paper configuration added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding paper configuration: {str(e)}')
        else:
            messages.error(request, 'Please correct errors below.')
        
        if exam_id:
            return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
        else:
            return redirect('Exam:subject-configurations', grade=grade)
    
    def _add_score_ranking(self, request, grade, exam_id=None):
        form = ScoreRankingForm(request.POST)
        if form.is_valid():
            try:
                # Get the subject config ID from the form
                subject_config_id = request.POST.get('subject_config_id')
                if subject_config_id:
                    subject_config = get_object_or_404(ExamSubjectConfiguration, id=subject_config_id)
                    # Verify this config belongs to the correct grade
                    if subject_config.subject.grade != grade:
                        messages.error(request, 'Invalid subject configuration.')
                        if exam_id:
                            return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
                        else:
                            return redirect('Exam:subject-configurations', grade=grade)
                    
                    ranking = form.save(commit=False)
                    ranking.subject = subject_config
                    ranking.save()
                    messages.success(request, f'Score ranking added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding score ranking: {str(e)}')
        else:
            # Debug: show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            messages.error(request, 'Please correct errors below.')
        
        if exam_id:
            return redirect('Exam:subject-configurations-with-exam', grade=grade, exam_id=exam_id)
        else:
            return redirect('Exam:subject-configurations', grade=grade)
    
    def _delete_item(self, request, action):
        try:
            if action == 'delete_subject_config':
                item_id = request.POST.get('item_id')
                config = get_object_or_404(ExamSubjectConfiguration, id=item_id)
                grade = config.subject.grade
                config.delete()
                messages.success(request, 'Subject configuration deleted successfully!')
            elif action == 'delete_paper':
                item_id = request.POST.get('item_id')
                paper = get_object_or_404(ExamSubjectPaper, id=item_id)
                grade = paper.exam_subject.subject.grade
                paper.delete()
                messages.success(request, 'Paper configuration deleted successfully!')
            elif action == 'delete_score_ranking':
                item_id = request.POST.get('item_id')
                ranking = get_object_or_404(ScoreRanking, id=item_id)
                grade = ranking.subject.subject.grade
                ranking.delete()
                messages.success(request, 'Score ranking deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting item: {str(e)}')
        
        # Check if this is an AJAX request or form submission
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        else:
            # For regular form submissions, redirect back to the same page
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            else:
                # Fallback redirect
                return redirect('Exam:exam-list')
