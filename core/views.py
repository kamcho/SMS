import json
import datetime
from datetime import datetime, date
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Avg, Sum, Case, When, F, FloatField
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import Student, StudentProfile, School, Class, Grade, AcademicYear, Term, ExamMode, TeacherClassProfile, AttendanceSession, StudentAttendance
from .forms import StudentForm, StudentProfileForm, AcademicYearForm, TermForm, GradeForm, ClassForm, ExamForm, ExamModeForm, PaymentForm, AttendanceSessionForm, StudentAttendanceForm
from Exam.models import ExamSUbjectScore, Exam, Subject
from accounts.models import Payment
from communication.models import Notification, PaymentNotification
from django.views.generic import TemplateView

class DashboardView(LoginRequiredMixin, ListView):
    model = Student
    template_name = 'core/dashboard.html'
    context_object_name = 'recent_students'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
            
        if request.user.role == 'Teacher':
            return redirect('core:teacher-dashboard')
            
        if request.user.role == 'Guardian':
            return redirect('core:guardian-dashboard')
                
        # Admins, Superusers, and default fallback see the main dashboard
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = Student.objects.all().select_related('studentprofile__school').order_by('-joined_date')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query) | 
                Q(adm_no__icontains=query)
            )
        return queryset[:7]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_students'] = Student.objects.count()
        context['search_query'] = self.request.GET.get('q', '')
        
        # Additional Stats for Dashboard
        context['total_teachers'] = TeacherClassProfile.objects.values('user').distinct().count()
        context['total_schools'] = School.objects.count()
        context['total_revenue'] = Payment.objects.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Chart Data: Gender Distribution
        gender_data = list(Student.objects.values('gender').annotate(count=Count('gender')))
        context['gender_dist_json'] = json.dumps([
            {'name': d['gender'].capitalize(), 'count': d['count']} for d in gender_data
        ])
        
        # Chart Data: School Distribution
        school_data = list(StudentProfile.objects.values('school__name').annotate(count=Count('school')).order_by('-count'))
        context['school_dist_json'] = json.dumps([
            {'name': d['school__name'] or 'Unassigned', 'count': d['count']} for d in school_data
        ])
        
        # Chart Data: Grade Distribution
        grade_data = list(StudentProfile.objects.values('class_id__grade__name').annotate(count=Count('class_id__grade')).order_by('class_id__grade__name'))
        context['grade_dist_json'] = json.dumps([
            {'name': d['class_id__grade__name'] or 'Unassigned', 'count': d['count']} for d in grade_data
        ])

        # Wall of Fame: Top Performing Students
        latest_exam = Exam.objects.order_by('-id').first()
        if latest_exam:
            top_performers = ExamSUbjectScore.objects.filter(paper__exam_subject__exam=latest_exam)\
                .values('student__id', 'student__first_name', 'student__last_name', 'student__adm_no')\
                .annotate(avg_score=Avg('score'))\
                .order_by('-avg_score')[:4]
            context['top_performers'] = top_performers
            context['target_exam'] = latest_exam

            # Grade Performance line graph data
            grade_perf = ExamSUbjectScore.objects.filter(paper__exam_subject__exam=latest_exam)\
                .values(name=F('student__studentprofile__class_id__grade__name'))\
                .annotate(avg=Avg('score'))\
                .order_by('name')
            
            context['grade_perf_json'] = json.dumps(list(grade_perf))

        return context

@login_required
def guardian_dashboard(request):
    if request.user.role != 'Guardian':
        return redirect('core:dashboard')
    
    # Get students linked to this guardian
    students = request.user.students.all().select_related('studentprofile__school', 'studentprofile__class_id__grade')
    
    # Get schools and grades associated with these students for filtering notifications
    school_ids = students.values_list('studentprofile__school_id', flat=True)
    grade_ids = students.values_list('studentprofile__class_id__grade_id', flat=True)
    
    # Filter notifications
    notifications = Notification.objects.filter(
        Q(target_type='all_schools') |
        Q(target_type='grade_all_schools', grade_id__in=grade_ids) |
        Q(target_type='certain_school', school_id__in=school_ids) |
        Q(target_type='grade_certain_school', school_id__in=school_ids, grade_id__in=grade_ids)
    ).select_related('school', 'grade', 'created_by').order_by('-created_at')[:10]
    
    # Payment notifications for linked students
    payment_notifications = PaymentNotification.objects.filter(student__in=students).order_by('-sent_at')[:5]
    
    # Calculate total fee balance
    total_balance = sum(student.studentprofile.fee_balance for student in students if hasattr(student, 'studentprofile'))
    
    return render(request, 'core/guardian_dashboard.html', {
        'students': students,
        'notifications': notifications,
        'payment_notifications': payment_notifications,
        'total_balance': total_balance
    })

class TeacherDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/teacher_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all class & subject assignments for this teacher
        assignments = TeacherClassProfile.objects.filter(
            user=self.request.user
        ).select_related('class_id', 'class_id__grade', 'subject')
        
        # Calculate distinct classes assigned to
        classes_assigned = set(a.class_id for a in assignments)
        
        # Calculate total students across all assigned classes
        total_unique_students = StudentProfile.objects.filter(
            class_id__in=[c.id for c in classes_assigned]
        ).values('student').distinct().count()
        
        context['assignments'] = assignments
        context['total_classes'] = len(classes_assigned)
        context['total_students'] = total_unique_students
        
        # Determine active exam via ExamMode
        from core.models import ExamMode
        active_mode = ExamMode.objects.filter(
            school=self.request.user.school,
            active=True
        ).select_related('exam').first()
        context['active_exam'] = active_mode.exam if active_mode else None

        from Exam.models import Exam
        context['latest_exam'] = Exam.objects.order_by('-id').first()
        
        return context


class StudentsListView(LoginRequiredMixin, ListView):
    model = Student
    template_name = 'core/students_list.html'
    context_object_name = 'students'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Student.objects.all().order_by('first_name', 'last_name')
        
        # Get search query
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query) | 
                Q(adm_no__icontains=query)
            )
        
        # Filter by school if user is not admin
        if not self.request.user.is_superuser:
            # Assuming user has a school field or profile with school
            # This is a placeholder - adjust based on your user model
            try:
                user_school = self.request.user.profile.school
                queryset = queryset.filter(studentprofile__school=user_school)
            except AttributeError:
                # If user doesn't have school, show all (or handle as needed)
                pass
        
        # Filter by school if specified
        school_id = self.request.GET.get('school')
        if school_id:
            queryset = queryset.filter(studentprofile__school_id=school_id)
        
        # Filter by class if specified
        class_id = self.request.GET.get('class')
        if class_id:
            queryset = queryset.filter(studentprofile__class_id=class_id)
        
        return queryset.select_related('studentprofile__school', 'studentprofile__class_id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['schools'] = School.objects.all()
        context['selected_school'] = self.request.GET.get('school', '')
        
        # Get classes for the selected school
        selected_school_id = self.request.GET.get('school')
        if selected_school_id:
            from .models import Class
            context['classes'] = Class.objects.filter(grade__school_id=selected_school_id)
        else:
            context['classes'] = []
        
        context['selected_class'] = self.request.GET.get('class', '')
        context['total_students'] = self.get_queryset().count()
        return context


def create_student(request):
    if request.method == 'POST':
        student_form = StudentForm(request.POST)
        profile_form = StudentProfileForm(request.POST)
        
        if student_form.is_valid() and profile_form.is_valid():
            student = student_form.save()
            profile = profile_form.save(commit=False)
            profile.student = student
            profile.save()
            
            messages.success(request, f'Student {student.first_name} {student.last_name} has been created successfully!')
            return redirect('create_student')
    else:
        student_form = StudentForm()
        profile_form = StudentProfileForm()
    
    context = {
        'student_form': student_form,
        'profile_form': profile_form,
    }
    return render(request, 'core/create_student.html', context)


class StudentDetailView(DetailView):
    model = Student
    template_name = 'core/student_detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        # Allow Superusers and non-Guardians (Admins, Teachers, etc)
        if request.user.is_superuser or request.user.role != 'Guardian':
            return super().dispatch(request, *args, **kwargs)
            
        # For Guardians, verify the student is in their 'students' many-to-many field
        student_id = kwargs.get('pk')
        if not request.user.students.filter(id=student_id).exists():
            return render(request, 'core/403_guardian.html', status=403)
            
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from Exam.models import Exam, ExamSUbjectScore
        
        # Fetch all available exams for the filter dropdown
        context['all_exams'] = Exam.objects.all().order_by('-year', '-term', '-id')
        
        # Handle exam filtering
        selected_exam_id = self.request.GET.get('exam_id')
        
        if selected_exam_id:
            try:
                selected_exam = Exam.objects.get(id=selected_exam_id)
            except Exam.DoesNotExist:
                selected_exam = Exam.objects.first()
        else:
            # Default to most recent exam this student has scores for
            latest_score = ExamSUbjectScore.objects.filter(student=self.object).order_by('-paper__exam_subject__exam_id').first()
            selected_exam = latest_score.exam if latest_score else Exam.objects.first()

        context['selected_exam'] = selected_exam
        
        # Fetch detailed profile
        context['profile'] = StudentProfile.objects.filter(student=self.object).first()
        
        # Fetch filtered exam scores with aggregation by subject
        if selected_exam:
            from Exam.models import ExamSubjectConfiguration
            from types import SimpleNamespace
            
            # 1. Fetch RAW scores for current exam
            scores_raw = ExamSUbjectScore.objects.filter(
                student=self.object, 
                paper__exam_subject__exam=selected_exam
            ).select_related('paper__exam_subject__subject', 'paper__exam_subject')
            
            # 2. Aggregate papers to subjects
            subject_results = {}
            for s in scores_raw:
                subj = s.paper.exam_subject.subject
                if subj.id not in subject_results:
                    # Get config to find max_score and rankings
                    config = ExamSubjectConfiguration.objects.filter(exam=selected_exam, subject=subj).first()
                    subject_results[subj.id] = {
                        'subject': subj,
                        'total_score': 0,
                        'max_score': config.max_score if config else 100,
                        'config': config
                    }
                subject_results[subj.id]['total_score'] += s.score
            
            # 3. Find the previous exam to calculate progress
            previous_score_query = ExamSUbjectScore.objects.filter(
                student=self.object
            ).exclude(paper__exam_subject__exam=selected_exam).order_by('-paper__exam_subject__exam__id').first()
            previous_exam = previous_score_query.exam if previous_score_query else None
            
            prev_subject_sums = {}
            if previous_exam:
                prev_scores_raw = ExamSUbjectScore.objects.filter(
                    student=self.object, paper__exam_subject__exam=previous_exam
                ).select_related('paper__exam_subject')
                for ps in prev_scores_raw:
                    sub_id = ps.paper.exam_subject.subject_id
                    prev_subject_sums[sub_id] = prev_subject_sums.get(sub_id, 0) + ps.score

            # 4. Final Processing & Grade Determination
            scores = []
            for subj_id, data in subject_results.items():
                perc = (data['total_score'] / data['max_score']) * 100 if data['max_score'] > 0 else 0
                
                # Determine Grade based on rankings or fallback
                grade = 'BE'
                if data['config']:
                    rankings = list(data['config'].get_score_rankings())
                    if rankings:
                        for r in rankings:
                            if r.min_score <= data['total_score'] <= r.max_score:
                                grade = r.grade
                                break
                    else:
                        if perc >= 70: grade = 'EE'
                        elif perc >= 60: grade = 'ME'
                        elif perc >= 50: grade = 'AE'
                else:
                    if perc >= 70: grade = 'EE'
                    elif perc >= 60: grade = 'ME'
                    elif perc >= 50: grade = 'AE'
                
                # Calculate diff compared to previous exam (using percentages)
                score_diff = None
                abs_score_diff = None
                if previous_exam and subj_id in prev_subject_sums:
                    p_total = prev_subject_sums[subj_id]
                    p_conf = ExamSubjectConfiguration.objects.filter(exam=previous_exam, subject_id=subj_id).first()
                    p_max = p_conf.max_score if p_conf else 100
                    p_perc = (p_total / p_max) * 100 if p_max > 0 else 0
                    
                    score_diff = round(perc - p_perc, 1)
                    abs_score_diff = abs(score_diff)
                
                # Map back to namespace for template access (score.subject.name)
                scores.append(SimpleNamespace(
                    subject=data['subject'],
                    score=round(perc, 1),
                    grade=grade,
                    score_diff=score_diff,
                    abs_score_diff=abs_score_diff
                ))

        else:
            scores = []
            
        context['exam_scores'] = scores
        
        # Fetch payment history
        context['payments'] = Payment.objects.filter(student=self.object).order_by('-date_paid')
        
        # Data for Subject Performance Chart (Progress Bars & Radar)
        context['subject_names'] = [score.subject.name for score in scores]
        context['subject_values'] = [int(score.score) for score in scores]
        context['subject_names_json'] = json.dumps(context['subject_names'])
        context['subject_values_json'] = json.dumps(context['subject_values'])
        
        # Calculate overall student average for the selected exam
        if context['subject_values']:
            context['student_average'] = round(sum(context['subject_values']) / len(context['subject_values']), 1)
        else:
            context['student_average'] = 0
            
        import calendar
        now = timezone.now()
        
        # Get month/year from request, default to current
        try:
            year = int(self.request.GET.get('year', now.year))
            month = int(self.request.GET.get('month', now.month))
        except (ValueError, TypeError):
            year = now.year
            month = now.month
            
        # Ensure valid month
        if month < 1 or month > 12:
            month = now.month
            year = now.year
        
        # Calculate Previous and Next month/year for navigation
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        
        # Don't allow navigating past current month (optional, but good for schools)
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        
        show_next = (year < now.year) or (year == now.year and month < now.month)

        context['prev_month_params'] = f"?exam_id={selected_exam_id or ''}&month={prev_month}&year={prev_year}"
        context['next_month_params'] = f"?exam_id={selected_exam_id or ''}&month={next_month}&year={next_year}" if show_next else None
        
        # Get all days in the currently viewed month
        start_weekday, num_days = calendar.monthrange(year, month)
        # start_weekday is 0 for Monday, so we adjust to 0 for Sunday if needed
        # Our template header is S M T W T F S
        # Sunday=0, Monday=1, ..., Saturday=6
        # calendar.monthrange returns 0 for Monday, 6 for Sunday
        # To align with S(0) M(1) ... we shift: (start_weekday + 1) % 7
        padding_days = (start_weekday + 1) % 7
        
        month_days = [date(year, month, day) for day in range(1, num_days + 1)]
        
        # Fetch this student's attendance for the viewed month
        monthly_attendance = StudentAttendance.objects.filter(
            student=self.object,
            session__date__year=year,
            session__date__month=month
        ).select_related('session')
        
        # Create a dictionary mapping date to status
        attendance_map = {record.session.date: record.status for record in monthly_attendance}
        
        # Metrics setup
        attendance_counts = {
            'Present': 0,
            'Late': 0,
            'Absent': 0,
            'Half Day': 0
        }
        
        # Build the calendar data structure with padding
        calendar_data = []
        # Add padding days
        for _ in range(padding_days):
            calendar_data.append({'day': '', 'status': None})
            
        for day_date in month_days:
            status = attendance_map.get(day_date, None)
            calendar_data.append({
                'date': day_date,
                'day': day_date.day,
                'status': status  # 'Present', 'Absent', 'Late', 'Half Day', or None
            })
            if status in attendance_counts:
                attendance_counts[status] += 1
            
        context['calendar_data'] = calendar_data
        context['attendance_counts'] = attendance_counts
        # Convert month number to name
        context['current_month'] = date(year, month, 1).strftime('%B %Y')
        
        # Calculate attendance percentage for the viewed month
        total_sessions = monthly_attendance.count()
        if total_sessions > 0:
            present_count = attendance_counts['Present'] + attendance_counts['Late'] + (attendance_counts['Half Day'] * 0.5)
            context['attendance_percentage'] = int((present_count / total_sessions) * 100)
        else:
            context['attendance_percentage'] = 0

        # Discipline Logic
        from core.models import StudentDiscipline
        
        context['discipline_records'] = StudentDiscipline.objects.filter(student=self.object).order_by('-date')
        
        try:
            profile = self.object.studentprofile
            context['discipline_score'] = profile.discipline
        except AttributeError:
            context['discipline_score'] = 100

        # Financial Summary
        context['total_paid'] = context['payments'].aggregate(Sum('amount'))['amount__sum'] or 0

        return context


class ClassesListView(LoginRequiredMixin, ListView):
    model = Class
    template_name = 'core/classes_list.html'
    context_object_name = 'classes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Class.objects.all().select_related('grade', 'grade__school')
        
        # Filter by school if user is not admin
        if not self.request.user.is_superuser:
            try:
                user_school = self.request.user.profile.school
                queryset = queryset.filter(grade__school=user_school)
            except AttributeError:
                # If user doesn't have school, show all (or handle as needed)
                pass
        
        # Filter by school if specified (admin only)
        if self.request.user.is_superuser:
            school_id = self.request.GET.get('school')
            if school_id:
                queryset = queryset.filter(grade__school_id=school_id)
        
        # Filter by grade if specified
        grade_id = self.request.GET.get('grade')
        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)
        
        # Search by class name
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(name__icontains=query)
        
        return queryset.annotate(student_count=Count('studentprofile'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        
        if self.request.user.is_superuser:
            context['schools'] = School.objects.all()
            context['selected_school'] = self.request.GET.get('school', '')
        else:
            context['schools'] = []
            context['selected_school'] = ''
        
        # Get grades for the selected school
        selected_school_id = self.request.GET.get('school')
        if selected_school_id:
            context['grades'] = Grade.objects.filter(school_id=selected_school_id)
        elif not self.request.user.is_superuser:
            # For non-admin users, show grades from their school
            try:
                user_school = self.request.user.profile.school
                context['grades'] = Grade.objects.filter(school=user_school)
            except AttributeError:
                context['grades'] = []
        else:
            context['grades'] = []
        
        context['selected_grade'] = self.request.GET.get('grade', '')
        context['total_classes'] = self.get_queryset().count()
        return context


class ClassDetailView(LoginRequiredMixin, DetailView):
    model = Class
    template_name = 'core/class_detail.html'
    context_object_name = 'class_obj'

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser and not (hasattr(request.user, 'role') and request.user.role == 'Admin'):
            messages.error(request, "Only administrators can assign teachers.")
            return redirect('core:class-detail', pk=kwargs.get('pk'))

        action = request.POST.get('action')
        if action == 'assign_teacher':
            subject_id = request.POST.get('subject_id')
            teacher_id = request.POST.get('teacher_id')
            class_obj = self.get_object()

            if not subject_id or not teacher_id:
                messages.error(request, "Subject and Teacher are required.")
            else:
                try:
                    from core.models import TeacherClassProfile
                    from users.models import MyUser
                    from Exam.models import Subject
                    
                    teacher = MyUser.objects.get(id=teacher_id)
                    subject = Subject.objects.get(id=subject_id)
                    
                    # Update or create assignment
                    assignment, created = TeacherClassProfile.objects.update_or_create(
                        class_id=class_obj,
                        subject=subject,
                        defaults={'user': teacher}
                    )
                    
                    messages.success(request, f"Teacher {teacher.get_full_name() or teacher.email} assigned to {subject.name} for {class_obj.name}.")
                except Exception as e:
                    messages.error(request, f"Error: {str(e)}")

        return redirect('core:class-detail', pk=kwargs.get('pk'))
    
    def get_queryset(self):
        queryset = Class.objects.all().select_related('grade', 'grade__school')
        
        # Filter by school if user is not admin
        if not self.request.user.is_superuser:
            try:
                user_school = self.request.user.profile.school
                queryset = queryset.filter(grade__school=user_school)
            except AttributeError:
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get students in this class
        context['students'] = StudentProfile.objects.filter(
            class_id=self.object
        ).select_related('student', 'school').order_by('student__first_name', 'student__last_name')
        
        context['student_count'] = context['students'].count()
        
        # Calculate statistics
        male_count = context['students'].filter(student__gender='male').count()
        female_count = context['students'].filter(student__gender='female').count()
        context['gender_stats'] = {
            'male': male_count,
            'female': female_count,
            'male_percentage': round((male_count / context['student_count'] * 100), 1) if context['student_count'] > 0 else 0,
            'female_percentage': round((female_count / context['student_count'] * 100), 1) if context['student_count'] > 0 else 0,
        }
        
        # Teacher Assignments & Exams for Score Entry
        from core.models import TeacherClassProfile
        from Exam.models import Exam, Subject
        from users.models import MyUser

        context['teacher_assignments'] = TeacherClassProfile.objects.filter(
            user=self.request.user, 
            class_id=self.object
        ).select_related('subject')
        
        # Debug: Print assignment info
        print(f"DEBUG: User {self.request.user.email}, Class {self.object.id}")
        print(f"DEBUG: Teacher assignments count: {context['teacher_assignments'].count()}")
        for assignment in context['teacher_assignments']:
            print(f"DEBUG: Assignment - {assignment.subject.name}")
        
        # Determine active exam via ExamMode
        from core.models import ExamMode
        active_mode = ExamMode.objects.filter(
            active=True
        ).select_related('exam').first()
        context['active_exam'] = active_mode.exam if active_mode else None
        
        # Debug: Print exam info
        print(f"DEBUG: Active exam: {context['active_exam']}")
        print(f"DEBUG: Latest exam: {context.get('latest_exam')}")
        
        # Fallback: Get most recent exam in the system
        context['latest_exam'] = Exam.objects.order_by('-id').first()

        # Admin View: Manage Teachers
        if self.request.user.is_superuser or (hasattr(self.request.user, 'role') and self.request.user.role == 'Admin'):
            # Fetch all subjects for this grade
            # Subject model has a 'grade' charfield (e.g. 'Grade 1', 'Grade 2')
            grade_name = self.object.grade.name
            subjects = Subject.objects.filter(grade=grade_name).order_by('name')
            
            # Get current assignments for this class
            class_assignments = TeacherClassProfile.objects.filter(
                class_id=self.object
            ).select_related('user', 'subject')
            
            # Map subjects to assigned teachers
            assignment_map = {a.subject_id: a.user for a in class_assignments}
            
            subject_teacher_list = []
            for sub in subjects:
                subject_teacher_list.append({
                    'subject': sub,
                    'teacher': assignment_map.get(sub.id)
                })
            
            context['subject_teacher_list'] = subject_teacher_list
            context['available_teachers'] = MyUser.objects.filter(role='Teacher').order_by('email')
            context['is_admin_view'] = True
        
        # Recent Attendance Sessions
        recent_attendance = AttendanceSession.objects.filter(
            class_id=self.object
        ).select_related('taken_by').order_by('-date', '-created_at')[:5]
        
        # Calculate attendance counts for each session
        attendance_summary = []
        attendance_dates = []
        attendance_rates = []
        
        # We'll reverse recent_attendance for chronolical chart plotting
        for session in reversed(recent_attendance):
            records = session.records.all()
            present_count = records.filter(status='Present').count()
            absent_count = records.filter(status='Absent').count()
            total_count = records.count()
            
            rate = round((present_count / total_count * 100), 1) if total_count > 0 else 0
            
            # Use original loop for top-down table, but we can reuse this summary
            # We'll insert at 0 for summary to keep table descending
            attendance_summary.insert(0, {
                'date': session.date,
                'taken_by': session.taken_by,
                'present_count': present_count,
                'absent_count': absent_count,
                'total_count': total_count,
                'rate': rate,
            })
            
            attendance_dates.append(session.date.strftime('%b %d'))
            attendance_rates.append(rate)
            
        context['recent_attendance'] = attendance_summary
        context['attendance_dates'] = json.dumps(attendance_dates)
        context['attendance_rates'] = json.dumps(attendance_rates)
        
        # Average Attendance
        if attendance_rates:
            context['avg_attendance'] = round(sum(attendance_rates) / len(attendance_rates), 1)
        else:
            context['avg_attendance'] = 0
            
        return context


def configurations(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to access configurations.')
        return redirect('core:dashboard')
    
    context = {
        'academic_years': AcademicYear.objects.all().order_by('-start_date'),
        'terms': Term.objects.all().order_by('id'),
        'grades': Grade.objects.all().select_related('school').order_by('name', 'school__name'),
        'classes': Class.objects.all().select_related('school', 'grade').order_by('grade__name', 'name'),
        'exams': Exam.objects.all().select_related('year', 'term').order_by('-year__start_date', 'term__name'),
        'exam_modes': ExamMode.objects.all().select_related('school'),
        'schools': School.objects.all(),
    }
    
    # Get forms for each model
    context['academic_year_form'] = AcademicYearForm()
    context['term_form'] = TermForm()
    context['grade_form'] = GradeForm()
    context['class_form'] = ClassForm()
    context['exam_form'] = ExamForm()
    context['exam_mode_form'] = ExamModeForm()
    
    return render(request, 'core/configurations.html', context)


def create_academic_year(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        form = AcademicYearForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Academic year created successfully!')
        else:
            messages.error(request, 'Error creating academic year. Please check the form.')
    
    return redirect('core:configurations')


def create_term(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        form = TermForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Term created successfully!')
        else:
            messages.error(request, 'Error creating term. Please check the form.')
    
    return redirect('core:configurations')


def create_grade(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        form = GradeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Grade level created successfully!')
        else:
            messages.error(request, 'Error creating grade level. Please check the form.')
    
    return redirect('core:configurations')


def create_class(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class created successfully!')
        else:
            messages.error(request, f'Error creating class: {form.errors}')
    
    return redirect('core:configurations')


def create_exam(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Exam created successfully!')
        else:
            messages.error(request, 'Error creating exam. Please check the form.')
    
    return redirect('core:configurations')


def update_exam_mode(request, exam_mode_id):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    exam_mode = get_object_or_404(ExamMode, id=exam_mode_id)
    
    if request.method == 'POST':
        form = ExamModeForm(request.POST, instance=exam_mode)
        if form.is_valid():
            form.save()
            messages.success(request, f'Exam mode for {exam_mode.school.name} updated successfully!')
        else:
            messages.error(request, 'Error updating exam mode. Please check the form.')
    
    return redirect('core:configurations')


def delete_item(request, model_type, item_id):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        if model_type == 'academic_year':
            item = get_object_or_404(AcademicYear, id=item_id)
            item_name = item.name
            item.delete()
            messages.success(request, f'Academic year "{item_name}" deleted successfully!')
        elif model_type == 'term':
            item = get_object_or_404(Term, id=item_id)
            item_name = item.name
            item.delete()
            messages.success(request, f'Term "{item_name}" deleted successfully!')
        elif model_type == 'grade':
            item = get_object_or_404(Grade, id=item_id)
            item_name = item.name
            item.delete()
            messages.success(request, f'Grade level "{item_name}" deleted successfully!')
        elif model_type == 'class':
            item = get_object_or_404(Class, id=item_id)
            item_name = item.name
            item.delete()
            messages.success(request, f'Class "{item_name}" deleted successfully!')
        elif model_type == 'exam':
            item = get_object_or_404(Exam, id=item_id)
            item_name = item.name
            item.delete()
            messages.success(request, f'Exam "{item_name}" deleted successfully!')
        elif model_type == 'exam_mode':
            item = get_object_or_404(ExamMode, id=item_id)
            item_name = f"Exam mode for {item.school.name}"
            item.delete()
            messages.success(request, f'{item_name} deleted successfully!')
    
    return redirect('core:configurations')


@login_required
def class_exam_analytics(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Get all students in this class
    students = StudentProfile.objects.filter(class_id=class_id).select_related('student')
    
    # Get all exam scores for students in this class
    exam_scores = ExamSUbjectScore.objects.filter(
        student__in=[sp.student for sp in students]
    ).select_related('student', 'paper__exam_subject__subject', 'paper__exam_subject__exam').order_by('paper__exam_subject__exam', 'paper__exam_subject__subject')
    
    # Get available exams and subjects for filtering
    exams = Exam.objects.all().select_related('year', 'term').order_by('-year__start_date', 'term__name')
    subjects = Subject.objects.filter(grade=class_obj.grade.name).order_by('name')
    
    # Get filter parameters
    selected_exam = request.GET.get('exam')
    selected_subject = request.GET.get('subject')
    
    # Apply filters
    if selected_exam:
        exam_scores = exam_scores.filter(paper__exam_subject__exam_id=selected_exam)
    if selected_subject:
        exam_scores = exam_scores.filter(paper__exam_subject__subject_id=selected_subject)
        
    # NEW: Fetch rankings if we have a specific subject filter
    from Exam.models import ExamSubjectConfiguration, ScoreRanking
    rankings = []
    if selected_subject and selected_exam:
        config = ExamSubjectConfiguration.objects.filter(exam_id=selected_exam, subject_id=selected_subject).first()
        if config:
            rankings = list(ScoreRanking.objects.filter(subject=config))

    def get_score_grade(score, student_grade_name):
        if rankings:
            for r in rankings:
                if r.min_score <= score <= r.max_score:
                    return r.grade
        
        # Fallback logic or for Grade 7/8/9
        if score >= 70: return 'EE'
        if score >= 60: return 'ME'
        if score >= 50: return 'AE'
        return 'BE'

    
    # Organize data for display
    analytics_data = {}
    
    # Get all subject configurations for this grade and exam context to help with ranking and max scores
    subject_configs = ExamSubjectConfiguration.objects.filter(
        subject__grade=class_obj.grade.name
    ).select_related('subject', 'exam')
    
    # Map for easy lookup: (exam_id, subject_id) -> (rankings, max_score)
    config_data_map = {}
    for config in subject_configs:
        config_data_map[(config.exam_id, config.subject_id)] = {
            'rankings': list(config.get_score_rankings()),
            'max_score': config.max_score or 100
        }

    for student_profile in students:
        student = student_profile.student
        student_scores = exam_scores.filter(student=student)
        
        # Get subject-wise scores (Summing papers)
        subject_scores = {}
        for score in student_scores:
            subject_obj = score.subject
            subject_name = subject_obj.name
            exam_obj = score.exam
            
            if subject_name not in subject_scores:
                subject_scores[subject_name] = {
                    'score': 0,
                    'grade': '',
                    'percentage': 0,
                    'exam': exam_obj.name,
                    'subject_id': subject_obj.id,
                    'exam_id': exam_obj.id
                }
            
            subject_scores[subject_name]['score'] += score.score
            
        # After summing all papers, calculate grades and percentages for each subject
        student_subject_percentages = []
        for s_name, s_data in subject_scores.items():
            s_total_score = s_data['score']
            conf = config_data_map.get((s_data['exam_id'], s_data['subject_id']), {})
            s_rankings = conf.get('rankings', [])
            s_max = conf.get('max_score', 100)
            
            # Calculate percentage based on CONFIG max score
            perc = (s_total_score / s_max) * 100 if s_max > 0 else 0
            s_data['percentage'] = round(perc, 1)
            student_subject_percentages.append(perc)
            
            best_grade = 'BE'
            if s_rankings:
                for r in s_rankings:
                    if r.min_score <= s_total_score <= r.max_score:
                        best_grade = r.grade
                        break
            else:
                # Fallback matching the model logic (based on percentage for fallback)
                if perc >= 70: best_grade = 'EE'
                elif perc >= 60: best_grade = 'ME'
                elif perc >= 50: best_grade = 'AE'
            
            s_data['grade'] = best_grade

        # Calculate total score and average of percentages
        total_score_sum = sum(s['score'] for s in subject_scores.values())
        avg_percentage = sum(student_subject_percentages) / len(student_subject_percentages) if student_subject_percentages else 0
        
        analytics_data[student.id] = {
            'student': student,
            'profile': student_profile,
            'total_score': total_score_sum,
            'avg_score': round(avg_percentage, 1),
            'subject_scores': subject_scores,
            'exam_count': student_scores.values('paper__exam_subject__exam').distinct().count()
        }
    
    # Calculate rankings
    if selected_exam and selected_subject:
        # Rank by specific exam and subject
        ranked_students = sorted(
            analytics_data.values(),
            key=lambda x: x['subject_scores'].get(
                Subject.objects.get(id=selected_subject).name, {}
            ).get('score', 0),
            reverse=True
        )
    elif selected_exam:
        # Rank by total score for specific exam
        ranked_students = sorted(
            analytics_data.values(),
            key=lambda x: x['total_score'],
            reverse=True
        )
    else:
        # Rank by overall average
        ranked_students = sorted(
            analytics_data.values(),
            key=lambda x: x['avg_score'],
            reverse=True
        )
    
    # Add ranks
    for rank, student_data in enumerate(ranked_students, 1):
        student_data['rank'] = rank
    
    # Get unique subjects for table headers
    if selected_subject:
        table_subjects = [get_object_or_404(Subject, id=selected_subject)]
    else:
        # Get all subjects defined for this grade level (e.g., PP1, Grade 1)
        grade_name = class_obj.grade.name
        table_subjects = list(Subject.objects.filter(grade=grade_name).order_by('name'))
        
        # If no subjects found for this grade name, fallback to subjects found in scores
        if not table_subjects:
            table_subjects = list(set(score.subject for score in exam_scores))
            table_subjects.sort(key=lambda x: x.name)

    # Attach max_score to each subject for the table header
    for subject in table_subjects:
        if selected_exam:
            conf = ExamSubjectConfiguration.objects.filter(exam_id=selected_exam, subject=subject).first()
            subject.max_score = conf.max_score if conf else 100
        else:
            # Fallback to the most recent configuration available for this subject
            conf = ExamSubjectConfiguration.objects.filter(subject=subject).order_by('-exam_id').first()
            subject.max_score = conf.max_score if conf else 100
    
    # Prepare display scores for the table to avoid using a 'lookup' filter
    for student_data in ranked_students:
        display_scores = []
        for subject in table_subjects:
            score_obj = student_data['subject_scores'].get(subject.name)
            display_scores.append(score_obj)
        student_data['display_scores'] = display_scores

    grade_counts = {'EE': 0, 'ME': 0, 'AE': 0, 'BE': 0}
    for s in ranked_students:
        avg = s['avg_score']
        g = get_score_grade(avg, class_obj.grade.name)
        if g in grade_counts:
            grade_counts[g] += 1

    # Calculate class average (average of student averages)
    total_avg = sum(s['avg_score'] for s in ranked_students)
    class_average = round(total_avg / len(ranked_students), 1) if ranked_students else 0

    # Calculate subject-wise averages for graphs and insights
    subject_performance = []
    for subject in table_subjects:
        # Get all scores for this specific subject across students
        relevant_configs = [c for k, c in config_data_map.items() if k[1] == subject.id]
        ref_max = relevant_configs[0]['max_score'] if relevant_configs else 100
        
        subject_student_percentages = []
        subject_student_raw_scores = []
        for s_data in ranked_students:
            score_item = s_data['subject_scores'].get(subject.name)
            if score_item:
                # Calculate percentage for THIS subject and THIS student
                student_s_max = config_data_map.get((score_item['exam_id'], subject.id), {}).get('max_score', ref_max)
                student_perc = (score_item['score'] / student_s_max) * 100 if student_s_max > 0 else 0
                subject_student_percentages.append(student_perc)
                subject_student_raw_scores.append(score_item['score'])
        
        s_avg_perc = sum(subject_student_percentages) / len(subject_student_percentages) if subject_student_percentages else 0
        s_avg_raw = sum(subject_student_raw_scores) / len(subject_student_raw_scores) if subject_student_raw_scores else 0
        
        subject_performance.append({
            'name': subject.name,
            'avg': round(s_avg_perc, 1),
            'raw_avg': round(s_avg_raw, 1),
            'grade': get_score_grade(s_avg_perc, class_obj.grade.name)
        })

    # Add a lookup-friendly version for the table footer
    subject_footer_stats = {s['name']: s for s in subject_performance}

    # Sort subject performance for insights
    sorted_performance = sorted(subject_performance, key=lambda x: x['avg'], reverse=True)
    best_subject = sorted_performance[0] if sorted_performance else None
    worst_subject = sorted_performance[-1] if sorted_performance else None

    context = {
        'class_obj': class_obj,
        'analytics_data': analytics_data,
        'ranked_students': ranked_students,
        'table_subjects': table_subjects,
        'class_average': class_average,
        'grade_counts': grade_counts,
        'subject_performance': subject_performance,
        'subject_footer_stats': subject_footer_stats,
        'best_subject': best_subject,
        'worst_subject': worst_subject,
        'subject_labels': [s['name'] for s in subject_performance],
        'subject_averages': [s['avg'] for s in subject_performance],
        'exams': exams,
        'subjects': subjects,
        'selected_exam': selected_exam,
        'report_exam_id': selected_exam or (ExamSUbjectScore.objects.filter(student__studentprofile__class_id=class_obj).order_by('-paper__exam_subject__exam__year__start_date').values_list('paper__exam_subject__exam_id', flat=True).first()),
        'selected_subject': selected_subject,
        'total_students': len(students),
    }
    
    # Calculate historical class performance trend
    # Get all exams that have scores for this class
    exam_ids = ExamSUbjectScore.objects.filter(
        student__studentprofile__class_id=class_obj
    ).values_list('paper__exam_subject__exam', flat=True).distinct()
    
    historical_exams = Exam.objects.filter(id__in=exam_ids).select_related('year', 'term').order_by('year__start_date', 'term__id', 'id')
    
    historical_labels = []
    historical_averages = []
    
    for ex in historical_exams:
        # Get all scores for this class in this exam
        ex_scores_raw = ExamSUbjectScore.objects.filter(
            paper__exam_subject__exam=ex,
            student__studentprofile__class_id=class_obj
        ).select_related('paper__exam_subject')
        
        # 1. Sum scores per student per subject
        # (student_id, subject_id) -> total_score
        student_subj_marks = {}
        # subject_id -> max_score
        subj_max_map = {}
        
        for score in ex_scores_raw:
            sid = score.student_id
            subid = score.paper.exam_subject.subject_id
            key = (sid, subid)
            if key not in student_subj_marks:
                student_subj_marks[key] = 0
            student_subj_marks[key] += score.score
            subj_max_map[subid] = score.paper.exam_subject.max_score or 100
            
        # 2. Convert to percentages per student and grouping by subject
        # subject_id -> list of percentages
        subj_pct_list = {}
        for (sid, subid), total_marks in student_subj_marks.items():
            m_max = subj_max_map[subid]
            pct = (total_marks / m_max) * 100 if m_max > 0 else 0
            if subid not in subj_pct_list:
                subj_pct_list[subid] = []
            subj_pct_list[subid].append(pct)
            
        # 3. Final average across all subjects and all students for THIS exam (Line Chart)
        # Average of subject averages
        exam_subj_averages = [sum(pcts)/len(pcts) for pcts in subj_pct_list.values() if pcts]
        ex_avg = sum(exam_subj_averages) / len(exam_subj_averages) if exam_subj_averages else 0
        
        historical_labels.append(f"{ex.name} ({ex.year.start_date.year})")
        historical_averages.append(round(ex_avg, 1))

        # Store subj_pct_list for radar usage to avoid re-querying or duplicate logic
        ex.cached_subj_averages = {subid: (sum(pcts)/len(pcts)) for subid, pcts in subj_pct_list.items()}
        
    # Radar Chart Data: Subject Performance Footprint
    # Radar Axes = Subjects, Datasets = Exams
    radar_labels = [s.name for s in table_subjects]
    radar_datasets = []
    colors = ['#3b82f6', '#f43f5e', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316']
    
    for i, ex in enumerate(historical_exams):
        ex_data = []
        # Use the averages we pre-calculated in the historical loop
        subj_averages = getattr(ex, 'cached_subj_averages', {})
        
        for subject in table_subjects:
            val = subj_averages.get(subject.id, 0)
            ex_data.append(round(val, 1))
        
        radar_datasets.append({
            'label': f"{ex.name} ({ex.year.start_date.year})",
            'data': ex_data,
            'borderColor': colors[i % len(colors)],
            'backgroundColor': colors[i % len(colors)] + '40',
            'fill': True,
            'borderWidth': 2,
            'pointRadius': 4,
            'pointHoverRadius': 6,
        })
        
    context['radar_labels_js'] = json.dumps(radar_labels)
    context['radar_datasets_js'] = json.dumps(radar_datasets)
    context['historical_labels_js'] = json.dumps(historical_labels)
    historical_averages_js = json.dumps(historical_averages)
    # Use the same name as current template expects but with better description
    context['subject_labels'] = historical_labels # For backward compat if needed
    context['subject_averages'] = historical_averages # For backward compat if needed
    context['historical_averages_js'] = historical_averages_js
    
    context['grade_labels_js'] = json.dumps(['EE', 'ME', 'AE', 'BE'])
    context['grade_data_js'] = json.dumps([grade_counts.get(g, 0) for g in ['EE', 'ME', 'AE', 'BE']])
    
    # Gender Distribution by Grade for Grouped Bar Chart
    # Use ranked_students (pre-calculated with averages) to determine grades
    gender_grade_data = {
        'male': {'EE': 0, 'ME': 0, 'AE': 0, 'BE': 0},
        'female': {'EE': 0, 'ME': 0, 'AE': 0, 'BE': 0}
    }
    for s in ranked_students:
        gen = s['student'].gender
        sc = s['avg_score']
        g = get_score_grade(sc, class_obj.grade.name)
        if gen in gender_grade_data:
            gender_grade_data[gen][g] += 1
            
    context['gender_labels_js'] = json.dumps(['EE', 'ME', 'AE', 'BE'])
    context['gender_male_data_js'] = json.dumps([gender_grade_data['male'][g] for g in ['EE', 'ME', 'AE', 'BE']])
    context['gender_female_data_js'] = json.dumps([gender_grade_data['female'][g] for g in ['EE', 'ME', 'AE', 'BE']])
    
    return render(request, 'core/class_exam_analytics.html', context)


def manage_fee_payments(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to access fee payment management.')
        return redirect('core:dashboard')
    
    # Get search query and date filters
    search_query = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Get students with their profiles and fee balances
    students = StudentProfile.objects.select_related('student', 'school', 'class_id').all()
    
    # Apply filters
    if search_query:
        students = students.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__middle_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__adm_no__icontains=search_query)
        )
    
    if date_from or date_to:
        payment_q = Q()
        if date_from:
            payment_q &= Q(student__payment__date_paid__gte=date_from)
        if date_to:
            payment_q &= Q(student__payment__date_paid__lte=date_to)
        students = students.filter(payment_q).distinct()
    
    # Apply role-based filtering
    if not request.user.is_superuser:
        try:
            user_school = request.user.profile.school
            students = students.filter(school=user_school)
        except AttributeError:
            pass  # Handle case where user profile doesn't have school
    
    # Order by name
    students = students.order_by('student__first_name', 'student__last_name')
    
    context = {
        'students': students,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'payment_form': PaymentForm(),
    }
    
    return render(request, 'core/manage_fee_payments.html', context)


def process_payment(request, student_id):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        messages.error(request, 'You do not have permission to process payments.')
        return redirect('core:manage-fee-payments')
    
    student = get_object_or_404(Student, id=student_id)
    student_profile = get_object_or_404(StudentProfile, student=student)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.student = student
            payment.recorded_by = request.user
            
            try:
                payment.save()
                
                # Automatically log a payment notification
                PaymentNotification.objects.create(
                    student=student,
                    payment=payment,
                    message=f"Dear Parent, we have received KES {payment.amount} for {student.first_name}. Your new balance is KES {student_profile.fee_balance}."
                )

                messages.success(request, f'Payment of {payment.amount} recorded successfully for {student.first_name} {student.last_name}')
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Payment of {payment.amount} recorded successfully',
                        'new_balance': student_profile.fee_balance
                    })
                    
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)})
                messages.error(request, f'Error processing payment: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = PaymentForm()
    
    # For AJAX requests, return the form HTML
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        context = {
            'form': form,
            'student': student,
            'student_profile': student_profile,
        }
        return render(request, 'core/partials/payment_modal.html', context)
    
    return redirect('core:manage-fee-payments')


def get_comparative_trend_data(subject, current_class, historical_exams):
    """
    Returns a list of datasets for Chart.js representing:
    1. Other classes in the same grade (across all schools)
    2. Overall grade benchmark (average of all classes)
    """
    from django.db.models import Avg
    from core.models import Class
    
    grade = current_class.grade
    all_classes_in_grade = Class.objects.filter(grade=grade).exclude(id=current_class.id).select_related('school')
    
    datasets = []
    
    # 1. Individual lines for other classes
    colors = ['rgba(59, 130, 246, 0.6)', 'rgba(16, 185, 129, 0.6)', 'rgba(245, 158, 11, 0.6)', 'rgba(139, 92, 246, 0.6)']
    for i, other_cl in enumerate(all_classes_in_grade[:4]): # Limit to 4 other classes for clarity
        cl_averages = []
        for ex in historical_exams:
            avg = ExamSUbjectScore.objects.filter(
                paper__exam_subject__exam=ex, paper__exam_subject__subject=subject, student__studentprofile__class_id=other_cl
            ).aggregate(Avg('score'))['score__avg'] or 0
            cl_averages.append(round(float(avg), 1))
        
        datasets.append({
            'label': f"{other_cl.name} ({other_cl.school.name})",
            'data': cl_averages,
            'borderColor': colors[i % len(colors)],
            'borderWidth': 1.5,
            'fill': False,
            'tension': 0.4,
            'pointRadius': 0
        })

    # 2. Grade-wide benchmark (Red broken line)
    grade_averages = []
    for ex in historical_exams:
        avg = ExamSUbjectScore.objects.filter(
            paper__exam_subject__exam=ex, 
            paper__exam_subject__subject=subject, 
            student__studentprofile__class_id__grade=grade
        ).aggregate(Avg('score'))['score__avg'] or 0
        grade_averages.append(round(float(avg), 1))
    
    datasets.append({
        'label': 'Grade Benchmark (All Schools)',
        'data': grade_averages,
        'borderColor': 'rgba(239, 68, 68, 0.8)', # Red
        'borderWidth': 2,
        'borderDash': [5, 5],
        'fill': False,
        'tension': 0.4,
        'pointRadius': 2,
        'pointBackgroundColor': '#ef4444'
    })
    
    return datasets

@login_required
def subject_exam_analytics(request, class_id, subject_id, exam_id):
    class_obj = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    exam = get_object_or_404(Exam, id=exam_id)
    
    # Get all students in this class
    students_profiles = StudentProfile.objects.filter(class_id=class_id).select_related('student')
    student_ids = [sp.student.id for sp in students_profiles]
    
    # Get scores for THIS exam
    current_scores = ExamSUbjectScore.objects.filter(
        paper__exam_subject__exam=exam,
        paper__exam_subject__subject=subject,
        student_id__in=student_ids
    ).select_related('student')
    
    # Calculate Grade distribution
    grade_counts = current_scores.values('grade').annotate(total=Count('id'))
    grades_data = {
        'EE': 0, 'ME': 0, 'AE': 0, 'BE': 0
    }
    for item in grade_counts:
        grades_data[item['grade']] = item['total']
        
    # Calculate Gender distribution
    gender_stats = current_scores.values('student__gender').annotate(
        avg_score=Avg('score'),
        count=Count('id')
    )
    
    # Average Score
    avg_score = current_scores.aggregate(Avg('score'))['score__avg'] or 0
    
    # Trend Logic: Performance across ALL exams for THIS subject & class
    subject_exams_ids = ExamSUbjectScore.objects.filter(
        paper__exam_subject__subject=subject,
        student__studentprofile__class_id=class_obj
    ).values_list('paper__exam_subject__exam_id', flat=True).distinct()
    
    subject_exams = Exam.objects.filter(id__in=subject_exams_ids).order_by('year__start_date', 'term__id', 'id')
    
    historical_labels = []
    historical_averages = []
    
    for ex in subject_exams:
        ex_scores = ExamSUbjectScore.objects.filter(
            paper__exam_subject__exam=ex,
            paper__exam_subject__subject=subject,
            student__studentprofile__class_id=class_obj
        )
        ex_avg = ex_scores.aggregate(Avg('score'))['score__avg'] or 0
        historical_labels.append(f"{ex.name} ({ex.year.start_date.year})")
        historical_averages.append(round(ex_avg, 1))

    # Prepare data for Student-wise Comparison (Current vs Previous)
    # Find the "previous" exam from the list of exams that actually have scores
    subject_exams_list = list(subject_exams)
    previous_exam = None
    try:
        current_index = subject_exams_list.index(exam)
        if current_index > 0:
            previous_exam = subject_exams_list[current_index - 1]
    except ValueError:
        # Fallback logic if current exam isn't in records yet
        previous_exam = Exam.objects.filter(
            year=exam.year
        ).filter(
            Q(term__id__lt=exam.term.id) | Q(id__lt=exam.id)
        ).order_by('-id').first()
    
    # Radar Chart Data: Subject Footprint across Classes for this Grade
    # Radar Axes = Classes, Datasets = Exams
    peer_classes = list(Class.objects.filter(grade=class_obj.grade).exclude(id=class_obj.id).select_related('school')[:4])
    all_radar_classes = [class_obj] + peer_classes
    radar_labels = [f"{c.name} ({c.school.name if c.school else ''})" for c in all_radar_classes]
    radar_datasets = []
    colors = ['#4f46e5', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316']
    
    for i, ex in enumerate(subject_exams):
        ex_data = []
        for c in all_radar_classes:
            p_avg = ExamSUbjectScore.objects.filter(
                paper__exam_subject__exam=ex, paper__exam_subject__subject=subject, student__studentprofile__class_id=c
            ).aggregate(Avg('score'))['score__avg'] or 0
            ex_data.append(round(float(p_avg), 1))
        
        radar_datasets.append({
            'label': f"{ex.name} ({ex.year.start_date.year})",
            'data': ex_data,
            'borderColor': colors[i % len(colors)],
            'backgroundColor': colors[i % len(colors)] + '10',
            'fill': True,
            'borderWidth': 2,
            'pointRadius': 4,
            'pointHoverRadius': 6,
        })
    
    prev_scores = []
    if previous_exam:
        prev_scores = ExamSUbjectScore.objects.filter(
            paper__exam_subject__exam=previous_exam,
            paper__exam_subject__subject=subject,
            student_id__in=student_ids
        ).select_related('student')

    # Keep old student-wise comparison but rename labels for clarity in template
    # Prepare data for Line Chart (Student performance in current exam)
    chart_labels = [s.student.first_name for s in current_scores[:12]]
    current_student_data = [s.score for s in current_scores[:12]]
    
    prev_data_map = {s.student_id: s.score for s in prev_scores}
    prev_student_data = [prev_data_map.get(s.student_id, 0) for s in current_scores[:12]]

    # Attach trend data to scores for the table
    scores_with_trend = current_scores.order_by('-score')
    for s in scores_with_trend:
        s.prev_score = prev_data_map.get(s.student_id)
        if s.prev_score is not None:
            s.trend = s.score - s.prev_score
        else:
            s.trend = None

    context = {
        'class_obj': class_obj,
        'subject': subject,
        'exam': exam,
        'scores': scores_with_trend,
        'grades_data': grades_data,
        'avg_score': round(avg_score, 1),
        'student_count': current_scores.count(),
        'gender_stats': gender_stats,
        'previous_exam': previous_exam,
        'available_exams': subject_exams,
        # JSON for charts
        'historical_labels_js': json.dumps(historical_labels),
        'historical_averages_js': json.dumps(historical_averages),
        'comparative_datasets_js': json.dumps(get_comparative_trend_data(subject, class_obj, subject_exams)),
        # Grade Distribution Data
        'grade_labels_js': json.dumps(['EE', 'ME', 'AE', 'BE']),
        'grade_data_js': json.dumps([grades_data.get(g, 0) for g in ['EE', 'ME', 'AE', 'BE']]),
        # Student Comparison Data (Current vs Prev)
        'chart_labels_js': json.dumps(chart_labels),
        'current_data_js': json.dumps(current_student_data),
        'prev_data_js': json.dumps(prev_student_data),
        'gender_labels_js': json.dumps(['EE', 'ME', 'AE', 'BE']),
        'gender_male_data_js': json.dumps([current_scores.filter(grade=g, student__gender='male').count() for g in ['EE', 'ME', 'AE', 'BE']]),
        'gender_female_data_js': json.dumps([current_scores.filter(grade=g, student__gender='female').count() for g in ['EE', 'ME', 'AE', 'BE']]),
        'radar_labels_js': json.dumps(radar_labels),
        'radar_datasets_js': json.dumps(radar_datasets),
    }
    
    return render(request, 'core/subject_exam_analytics.html', context)


@login_required
def student_report(request, student_id, exam_id):
    from Exam.models import Exam, ExamSUbjectScore, ExamSubjectConfiguration
    from datetime import datetime
    student = get_object_or_404(Student, id=student_id)
    exam = get_object_or_404(Exam, id=exam_id)
    profile = StudentProfile.objects.filter(student=student).first()
    
    # Get all scores for this student and exam
    scores_raw = ExamSUbjectScore.objects.filter(
        student=student, 
        paper__exam_subject__exam=exam
    ).select_related('paper__exam_subject__subject')
    
    # Aggregate papers to subjects
    subject_data = {}
    for score in scores_raw:
        subj = score.paper.exam_subject.subject
        if subj.id not in subject_data:
            config = ExamSubjectConfiguration.objects.filter(exam=exam, subject=subj).first()
            subject_data[subj.id] = {
                'name': subj.name,
                'score': 0,
                'max': config.max_score if config else 100,
                'grade': ''
            }
        subject_data[subj.id]['score'] += score.score

    # Calculate percentages and grades
    total_percentages = []
    for subj_id, data in subject_data.items():
        perc = (data['score'] / data['max']) * 100 if data['max'] > 0 else 0
        total_percentages.append(perc)
        
        # Determine grade for this aggregated subject score
        config = ExamSubjectConfiguration.objects.filter(exam=exam, subject_id=subj_id).first()
        if config:
            ranking = config.scoreranking_set.filter(min_score__lte=data['score'], max_score__gte=data['score']).first()
            if ranking:
                data['grade'] = ranking.grade
            else:
                # Fallback
                if perc >= 80: data['grade'] = 'EE'
                elif perc >= 60: data['grade'] = 'ME'
                elif perc >= 40: data['grade'] = 'AE'
                else: data['grade'] = 'BE'
        else:
            if perc >= 80: data['grade'] = 'EE'
            elif perc >= 60: data['grade'] = 'ME'
            elif perc >= 40: data['grade'] = 'AE'
            else: data['grade'] = 'BE'

    student_average = round(sum(total_percentages) / len(total_percentages), 1) if total_percentages else 0
    
    context = {
        'student': student,
        'exam': exam,
        'profile': profile,
        'class_obj': profile.class_id,
        'subject_results': subject_data.values(),
        'student_average': student_average,
        'today': datetime.now().date(),
    }
    return render(request, 'core/student_report.html', context)


@login_required
def bulk_class_reports(request, class_id, exam_id):
    from Exam.models import Exam, ExamSUbjectScore, ExamSubjectConfiguration
    from datetime import datetime
    class_obj = get_object_or_404(Class, id=class_id)
    exam = get_object_or_404(Exam, id=exam_id)
    
    student_profiles = StudentProfile.objects.filter(class_id=class_obj).select_related('student', 'school')
    
    reports = []
    today = datetime.now().date()
    
    # Pre-fetch all configurations for this exam to avoid N+1 queries
    configs = ExamSubjectConfiguration.objects.filter(exam=exam).select_related('subject')
    config_dict = {c.subject_id: c for c in configs}
    
    for profile in student_profiles:
        student = profile.student
        scores_raw = ExamSUbjectScore.objects.filter(
            student=student, 
            paper__exam_subject__exam=exam
        ).select_related('paper__exam_subject__subject')
        
        subject_data = {}
        for score in scores_raw:
            subj_id = score.paper.exam_subject.subject_id
            if subj_id not in subject_data:
                config = config_dict.get(subj_id)
                subject_data[subj_id] = {
                    'name': score.paper.exam_subject.subject.name,
                    'score': 0,
                    'max': config.max_score if config else 100,
                    'grade': '',
                    'config': config
                }
            subject_data[subj_id]['score'] += score.score

        total_percentages = []
        for subj_id, data in subject_data.items():
            perc = (data['score'] / data['max']) * 100 if data['max'] > 0 else 0
            total_percentages.append(perc)
            
            config = data['config']
            if config:
                ranking = config.scoreranking_set.filter(min_score__lte=data['score'], max_score__gte=data['score']).first()
                if ranking:
                    data['grade'] = ranking.grade
                else:
                    if perc >= 80: data['grade'] = 'EE'
                    elif perc >= 60: data['grade'] = 'ME'
                    elif perc >= 40: data['grade'] = 'AE'
                    else: data['grade'] = 'BE'
            else:
                if perc >= 80: data['grade'] = 'EE'
                elif perc >= 60: data['grade'] = 'ME'
                elif perc >= 40: data['grade'] = 'AE'
                else: data['grade'] = 'BE'

        student_average = round(sum(total_percentages) / len(total_percentages), 1) if total_percentages else 0
        
        reports.append({
            'student': student,
            'profile': profile,
            'subject_results': subject_data.values(),
            'student_average': student_average,
        })
    
    context = {
        'class_obj': class_obj,
        'exam': exam,
        'reports': reports,
        'today': today,
    }
    return render(request, 'core/bulk_reports.html', context)


def mark_attendance(request, class_id=None):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role not in ['Admin', 'Teacher']:
        messages.error(request, 'You do not have permission to mark attendance.')
        return redirect('core:dashboard')
    
    selected_class = None
    selected_date = None
    students = []
    attendance_records = {}
    existing_session = None
    
    # If class_id is provided, get the class and auto-load students
    if class_id:
        try:
            selected_class = Class.objects.get(id=class_id)
            # Check user permissions for this class
            if not request.user.is_superuser:
                try:
                    user_school = request.user.profile.school
                    if selected_class.grade.school != user_school:
                        messages.error(request, 'You do not have permission to mark attendance for this class.')
                        return redirect('core:dashboard')
                except AttributeError:
                    pass
            
            # Auto-set today's date if not provided (only allow today's date)
            date_from_post = request.POST.get('date')
            date_from_get = request.GET.get('date')
            today = timezone.now().date()
            
            # Only allow today's date for attendance marking
            if date_from_post:
                try:
                    selected_date = datetime.strptime(date_from_post, '%Y-%m-%d').date()
                    if selected_date != today:
                        selected_date = today
                        messages.info(request, 'Attendance can only be marked for today. Date set to today.')
                except ValueError:
                    selected_date = today
            elif date_from_get:
                try:
                    selected_date = datetime.strptime(date_from_get, '%Y-%m-%d').date()
                    if selected_date != today:
                        selected_date = today
                        messages.info(request, 'Attendance can only be marked for today. Date set to today.')
                except ValueError:
                    selected_date = today
            else:
                selected_date = today
            
            # Always check if attendance session already exists for today
            session = AttendanceSession.objects.filter(
                class_id=selected_class,
                date=selected_date
            ).select_related('taken_by').first()
            
            if session:
                # Session exists - load existing records for editing
                existing_session = session
                attendance_records_list = list(session.records.select_related('student').all())
                created = False
            else:
                # No session exists yet - create new one when form is submitted
                existing_session = None
                attendance_records_list = []
                created = True
            
            # Get students for the selected class
            students = StudentProfile.objects.filter(class_id=selected_class).select_related('student').order_by('student__first_name')
            
            # Process attendance submission
            if request.method == 'POST' and 'submit_attendance' in request.POST:
                selected_students = request.POST.getlist('selected_students', [])
                
                # Debug: Print selected students
                print(f"Selected students: {selected_students}")
                print(f"Total students: {students.count()}")
                print(f"Session exists: {session is not None}")
                
                # Create session if it doesn't exist
                if not session:
                    session = AttendanceSession.objects.create(
                        class_id=selected_class,
                        date=selected_date,
                        taken_by=request.user
                    )
                    existing_session = session
                
                for student_profile in students:
                    student_id = str(student_profile.student.id)  # Convert to string for comparison
                    status = request.POST.get(f'status_{student_id}', 'Present')
                    remarks = request.POST.get(f'remarks_{student_id}', '')
                    
                    # Debug: Print each student's status
                    print(f"Student {student_id}: checkbox={student_id in selected_students}, status={status}")
                    
                    if student_id in selected_students:
                        # Student is selected (use dropdown status)
                        status = request.POST.get(f'status_{student_id}', 'Present')
                    else:
                        # Student is not selected (marked as absent)
                        status = 'Absent'
                    
                    if student_id in attendance_records:
                        # Update existing record
                        record = attendance_records[student_id]
                        record.status = status
                        record.remarks = remarks
                        record.save()
                    else:
                        # Create new record using update_or_create to handle duplicates
                        StudentAttendance.objects.update_or_create(
                            session=session,
                            student_id=student_profile.student.id,
                            defaults={
                                'status': status,
                                'remarks': remarks
                            }
                        )
                
                action = "updated" if not created else "marked"
                messages.success(request, f'Attendance {action} successfully for {selected_class.name} on {selected_date}')
                return redirect('core:class-detail', pk=selected_class.id)
        
        except Class.DoesNotExist:
            messages.error(request, 'Class not found.')
            return redirect('core:dashboard')
    
    # Handle form submission for class selection
    if request.method == 'POST' and 'select_class' in request.POST:
        form = AttendanceSessionForm(request.POST, user=request.user)
        if form.is_valid():
            selected_class = form.cleaned_data['class_id']
            selected_date = form.cleaned_data['date']
            return redirect('core:mark-attendance', class_id=selected_class.id, date=selected_date.isoformat())
    else:
        form = AttendanceSessionForm(user=request.user)
    
    context = {
        'form': form,
        'students': students,
        'selected_class': selected_class,
        'selected_date': selected_date,
        'attendance_records_list': attendance_records_list,
        'session': session,
        'existing_session': existing_session,
    }
    
    return render(request, 'core/mark_attendance.html', context)


def attendance_detail(request, class_id, date):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role not in ['Admin', 'Teacher']:
        messages.error(request, 'You do not have permission to view attendance details.')
        return redirect('core:dashboard')
    
    try:
        # Parse date from URL
        attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get class
        selected_class = Class.objects.get(id=class_id)
        
        # Check user permissions for this class
        if not request.user.is_superuser:
            try:
                user_school = request.user.profile.school
                if selected_class.grade.school != user_school:
                    messages.error(request, 'You do not have permission to view attendance for this class.')
                    return redirect('core:dashboard')
            except AttributeError:
                pass
        
        # Get attendance session
        session = get_object_or_404(AttendanceSession, class_id=selected_class, date=attendance_date)
        
        # Get attendance records with student details
        attendance_records = session.records.select_related('student', 'student__studentprofile').order_by('student__first_name')
        
        # Calculate statistics
        total_students = attendance_records.count()
        present_count = attendance_records.filter(status='Present').count()
        absent_count = attendance_records.filter(status='Absent').count()
        late_count = attendance_records.filter(status='Late').count()
        half_day_count = attendance_records.filter(status='Half Day').count()
        
        # Calculate percentages
        present_percentage = round((present_count / total_students * 100), 1) if total_students > 0 else 0
        absent_percentage = round((absent_count / total_students * 100), 1) if total_students > 0 else 0
        late_percentage = round((late_count / total_students * 100), 1) if total_students > 0 else 0
        half_day_percentage = round((half_day_count / total_students * 100), 1) if total_students > 0 else 0
        
        # Group by status for display
        status_groups = {
            'Present': attendance_records.filter(status='Present'),
            'Late': attendance_records.filter(status='Late'),
            'Half Day': attendance_records.filter(status='Half Day'),
            'Absent': attendance_records.filter(status='Absent'),
        }
        
        context = {
            'session': session,
            'class_obj': selected_class,
            'attendance_date': attendance_date,
            'attendance_records': attendance_records,
            'status_groups': status_groups,
            'statistics': {
                'total': total_students,
                'present': present_count,
                'absent': absent_count,
                'late': late_count,
                'half_day': half_day_count,
                'present_percentage': present_percentage,
                'absent_percentage': absent_percentage,
                'late_percentage': late_percentage,
                'half_day_percentage': half_day_percentage,
            }
        }
        
        return render(request, 'core/attendance_detail.html', context)
        
    except (ValueError, Class.DoesNotExist, AttendanceSession.DoesNotExist):
        messages.error(request, 'Attendance session not found.')
        return redirect('core:class-detail', pk=class_id)


def get_attendance_data(request):
    """AJAX endpoint to get attendance data for a class and date"""
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role not in ['Admin', 'Teacher']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    class_id = request.GET.get('class_id')
    date = request.GET.get('date')
    
    if not class_id or not date:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        selected_class = Class.objects.get(id=class_id)
        selected_date = date
        
        # Get or create attendance session
        session, created = AttendanceSession.objects.get_or_create(
            class_id=selected_class,
            date=selected_date,
            defaults={'taken_by': request.user}
        )
        
        # Get existing attendance records
        attendance_records = {}
        for record in session.records.all():
            attendance_records[record.student.id] = {
                'status': record.status,
                'remarks': record.remarks or ''
            }
        
        # Get students for the selected class
        students = StudentProfile.objects.filter(class_id=selected_class).select_related('student').order_by('student__first_name')
        
        student_data = []
        for student_profile in students:
            student_id = student_profile.student.id
            student_data.append({
                'id': student_id,
                'name': f"{student_profile.student.first_name} {student_profile.student.last_name}",
                'adm_no': student_profile.student.adm_no,
                'status': attendance_records.get(student_id, {}).get('status', 'Present'),
                'remarks': attendance_records.get(student_id, {}).get('remarks', ''),
            })
        
        return JsonResponse({
            'students': student_data,
            'session_created': created,
            'session_id': session.id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def schools_analytics(request):
    from Exam.models import Exam, Subject, ExamSUbjectScore
    from core.models import Grade, Class, StudentProfile
    from django.db.models import Sum
    
    # Get distinct grade names for selection
    grade_choices = [c[0] for c in Grade.choices]
    
    selected_grade_name = request.GET.get('grade')
    
    exams = Exam.objects.all().select_related('year', 'term').order_by('-year__start_date', 'term__name')
    
    analytics_data = []

    if selected_grade_name:
        subjects = Subject.objects.filter(grade=selected_grade_name).order_by('name')
        
        for exam in exams:
            exam_scores_exist = ExamSUbjectScore.objects.filter(
                paper__exam_subject__exam=exam,
                paper__exam_subject__subject__grade=selected_grade_name
            ).exists()
            
            if not exam_scores_exist:
                continue
                
            exam_data = {
                'exam': exam,
                'subjects': subjects,
                'class_rows': []
            }
            
            classes = Class.objects.filter(grade__name=selected_grade_name).select_related('school')
            
            for cls in classes:
                student_profiles = StudentProfile.objects.filter(class_id=cls)
                student_ids = student_profiles.values_list('student_id', flat=True)
                
                if not student_ids:
                    continue
                
                row = {
                    'class_name': cls.name,
                    'school_name': cls.school.name if cls.school else '',
                    'scores': [],
                    'total_mean': 0
                }
                
                has_any_score = False
                total_sum = 0
                
                for subject in subjects:
                    student_subject_totals = ExamSUbjectScore.objects.filter(
                        student_id__in=student_ids,
                        paper__exam_subject__exam=exam,
                        paper__exam_subject__subject=subject
                    ).values('student_id').annotate(total_score=Sum('score'))
                    
                    if student_subject_totals:
                        mean_score = sum(item['total_score'] for item in student_subject_totals) / len(student_subject_totals)
                        has_any_score = True
                    else:
                        mean_score = 0
                        
                    row['scores'].append(round(mean_score, 2))
                    total_sum += mean_score
                    
                if has_any_score:
                    row['total_mean'] = round(total_sum, 2)
                    exam_data['class_rows'].append(row)
            
            if exam_data['class_rows']:
                highest_scores = []
                for i in range(len(subjects)):
                    col_scores = [row['scores'][i] for row in exam_data['class_rows'] if row['scores'][i] > 0]
                    highest_scores.append(max(col_scores) if col_scores else 0)
                
                for row in exam_data['class_rows']:
                    tagged_scores = []
                    for i, score in enumerate(row['scores']):
                        is_highest = (score == highest_scores[i] and score > 0)
                        tagged_scores.append({
                            'value': score,
                            'is_highest': is_highest
                        })
                    row['scores'] = tagged_scores

                exam_data['class_rows'].sort(key=lambda x: x['total_mean'], reverse=True)
                analytics_data.append(exam_data)
                
    context = {
        'grade_choices': grade_choices,
        'selected_grade_name': selected_grade_name,
        'analytics_data': analytics_data,
    }
    
    return render(request, 'core/schools_analytics.html', context)

@login_required
def discipline_log(request):
    incidents = StudentDiscipline.objects.select_related('student', 'student__studentprofile__class_id', 'reported_by').order_by('-date')
    students = Student.objects.all().order_by('first_name')
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        severity = request.POST.get('severity')
        description = request.POST.get('description')
        action = request.POST.get('action_taken')
        
        student = get_object_or_404(Student, id=student_id)
        
        StudentDiscipline.objects.create(
            student=student,
            severity=severity,
            description=description,
            action_taken=action,
            reported_by=request.user
        )
        messages.success(request, f"Discipline incident logged for {student.first_name}.")
        return redirect('core:discipline-log')
        
    return render(request, 'core/discipline_log.html', {
        'incidents': incidents,
        'students': students,
        'severities': ['Minor', 'Moderate', 'Severe']
    })

@login_required
def delete_discipline(request, incident_id):
    incident = get_object_or_404(StudentDiscipline, id=incident_id)
    student_name = incident.student.first_name
    incident.delete()
    messages.success(request, f"Discipline record for {student_name} deleted.")
    return redirect('core:discipline-log')
