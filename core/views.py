import json
import datetime
from datetime import datetime, date, timedelta
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Avg, Sum, Case, When, F, FloatField, ExpressionWrapper
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import Student, StudentProfile, School,StudentDiscipline, Class, Grade, AcademicYear, Term, ExamMode, TeacherClassProfile, AttendanceSession, StudentAttendance, PromotionHistory
from .forms import StudentForm, StudentProfileForm, AcademicYearForm, TermForm, GradeForm, ClassForm, ExamForm, ExamModeForm, PaymentForm, AttendanceSessionForm, StudentAttendanceForm
from Exam.models import ExamSUbjectScore, Exam, Subject, ExamSubjectConfiguration, ScoreRanking
from decimal import Decimal
from accounts.models import Payment, FeeStructure, Invoice
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

        # Wall of Fame & Performance Graph Filtering
        all_exams = Exam.objects.all().order_by('-id')
        context['exams'] = all_exams
        
        selected_exam_id = self.request.GET.get('exam_id')
        target_exam = None
        
        if selected_exam_id:
            try:
                target_exam = Exam.objects.get(id=selected_exam_id)
            except (Exam.DoesNotExist, ValueError):
                target_exam = all_exams.first()
        else:
            target_exam = all_exams.first()
            
        context['target_exam'] = target_exam

        if target_exam:
            # Wall of Fame: Top Performing Students
            top_performers = ExamSUbjectScore.objects.filter(paper__exam_subject__exam=target_exam)\
                .values('student__id', 'student__first_name', 'student__last_name', 'student__adm_no')\
                .annotate(avg_score=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))\
                .order_by('-avg_score')[:4]
            context['top_performers'] = top_performers

            # Grade Performance line graph data
            grade_perf = ExamSUbjectScore.objects.filter(paper__exam_subject__exam=target_exam)\
                .values(name=F('student__studentprofile__class_id__grade__name'))\
                .annotate(avg=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))\
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
    
    # Financial log (Invoices and Payments)
    from accounts.models import Payment, Invoice, FeeStructure
    student_payments = Payment.objects.filter(student__in=students)
    student_invoices = Invoice.objects.filter(student__in=students)
    
    # Fee structures related to the guardian's students' grades
    fee_structures = FeeStructure.objects.filter(
        grade__id__in=grade_ids
    ).select_related('term').prefetch_related('grade').distinct().order_by('-created_at')[:10]
    
    financial_log = []
    for p in student_payments:
        financial_log.append({
            'type': 'payment',
            'student_name': p.student.first_name,
            'description': 'Fee Payment',
            'amount': p.amount,
            'date': p.date_paid,
            'sort_date': p.created_at if hasattr(p, 'created_at') else timezone.now(),
        })
    for i in student_invoices:
        if hasattr(i, 'fee_structure') and i.fee_structure:
            desc = f"Billed: {i.fee_structure.term.name}"
        else:
            desc = i.description or "General Billing"
            
        financial_log.append({
            'type': 'invoice',
            'student_name': i.student.first_name,
            'description': desc,
            'amount': i.amount,
            'date': i.created_at.date() if hasattr(i, 'created_at') else timezone.now().date(),
            'sort_date': i.created_at if hasattr(i, 'created_at') else timezone.now(),
        })
        
    financial_log.sort(key=lambda x: x['sort_date'], reverse=True)
    financial_log = financial_log[:15]
    
    # Calculate total fee balance
    total_balance = sum(student.studentprofile.fee_balance for student in students if hasattr(student, 'studentprofile'))
    
    # Attendance statistics
    from core.models import StudentAttendance
    attendance_records = StudentAttendance.objects.filter(student__in=students)
    
    present_count = attendance_records.filter(status='Present').count()
    late_count = attendance_records.filter(status='Late').count()
    absent_count = attendance_records.filter(status='Absent').count()
    
    total_attendance = present_count + late_count + absent_count
    
    if total_attendance > 0:
        attendance_percentage = int(((present_count + (late_count * 0.5)) / total_attendance) * 100)
    else:
        attendance_percentage = 0
    
    return render(request, 'core/guardian_dashboard.html', {
        'students': students,
        'notifications': notifications,
        'payment_notifications': payment_notifications,
        'financial_log': financial_log,
        'fee_structures': fee_structures,
        'total_balance': total_balance,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'total_attendance': total_attendance,
        'attendance_percentage': attendance_percentage,
    })

class TeacherDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/teacher_dashboard.html'
    
    def get_context_data(self, **kwargs):
        from Exam.models import Exam
        context = super().get_context_data(**kwargs)
        
        # Get all class & subject assignments for this teacher
        assignments = TeacherClassProfile.objects.filter(
            user=self.request.user
        ).select_related('class_id', 'class_id__grade', 'class_id__school', 'subject')
        
        # Calculate distinct classes assigned to
        classes_assigned = list(set(a.class_id for a in assignments))
        
        # Calculate distinct subjects taught
        subjects_taught = set(a.subject_id for a in assignments)
        
        # Calculate total students across all assigned classes
        class_ids = [c.id for c in classes_assigned]
        total_unique_students = StudentProfile.objects.filter(
            class_id__in=class_ids
        ).values('student').distinct().count()
        
        # Per-class student counts for chart
        class_student_data = []
        for cls in classes_assigned:
            count = StudentProfile.objects.filter(class_id=cls).count()
            class_student_data.append({
                'name': cls.name,
                'grade': cls.grade.name if cls.grade else '',
                'count': count,
                'id': cls.id,
            })
        class_student_data.sort(key=lambda x: x['name'])
        
        # Gender distribution across assigned classes
        male_count = StudentProfile.objects.filter(
            class_id__in=class_ids, student__gender='male'
        ).count()
        female_count = StudentProfile.objects.filter(
            class_id__in=class_ids, student__gender='female'
        ).count()
        
        # Recent attendance sessions for assigned classes
        recent_attendance = AttendanceSession.objects.filter(
            class_id__in=class_ids
        ).select_related('class_id', 'taken_by').order_by('-date', '-created_at')[:8]
        
        attendance_summary = []
        for session in recent_attendance:
            records = session.records.all()
            present = records.filter(status='Present').count()
            absent = records.filter(status='Absent').count()
            total = records.count()
            rate = round((present / total * 100), 1) if total > 0 else 0
            attendance_summary.append({
                'date': session.date,
                'class_name': session.class_id.name,
                'taken_by': session.taken_by,
                'present': present,
                'absent': absent,
                'total': total,
                'rate': rate,
            })
        
        # School name
        school_name = ''
        if hasattr(self.request.user, 'school') and self.request.user.school:
            school_name = self.request.user.school.name
            
        # Build unified assignments for the "My Assignments" table
        from django.db.models import Q
        from core.models import Class
        role_classes = Class.objects.filter(
            Q(class_teacher=self.request.user) | Q(invigilator=self.request.user)
        ).select_related('grade', 'school')

        invigilator_classes = Class.objects.filter(
            invigilator=self.request.user
        ).select_related('grade', 'school')

        unified_assignments = []
        for a in assignments:
            unified_assignments.append({
                'class_obj': a.class_id,
                'role': a.subject.name if a.subject else 'Subject Teacher',
            })
            
        for c in role_classes:
            roles = []
            if c.class_teacher == self.request.user:
                roles.append('Class Teacher')
            if c.invigilator == self.request.user:
                roles.append('Invigilator')
            
            # Prevent perfectly identical assignments (though they differ by role, merging them could be done, but distinct is fine)
            unified_assignments.append({
                'class_obj': c,
                'role': ' & '.join(roles),
            })
        
        context['assignments'] = assignments
        context['all_assignments'] = unified_assignments
        context['total_classes'] = len(classes_assigned)
        context['total_students'] = total_unique_students
        context['total_subjects'] = len(subjects_taught)
        context['class_student_data'] = class_student_data
        context['class_names_json'] = json.dumps([d['name'] for d in class_student_data])
        context['class_counts_json'] = json.dumps([d['count'] for d in class_student_data])
        context['male_count'] = male_count
        context['female_count'] = female_count
        context['recent_attendance'] = attendance_summary
        context['school_name'] = school_name
        # Determine active exam: prioritize ExamMode, fall back to latest running exam
        exam_mode = ExamMode.objects.select_related('exam').first()
        active_exam = None
        if exam_mode and exam_mode.active and exam_mode.exam and exam_mode.exam.is_running:
            active_exam = exam_mode.exam
        
        if not active_exam:
            # Fallback to the latest exam marked as running
            active_exam = Exam.objects.filter(is_running=True).order_by('-id').first()
            
        context['active_exam'] = active_exam

        invigilated_data = []
        if active_exam:
            # Get exams
            # Use invigilator_classes strictly for score entry modal
            for c in invigilator_classes:
                # Use active exam configurations to find relevant subjects for this grade
                configs = ExamSubjectConfiguration.objects.filter(
                    exam=active_exam,
                    subject__grade=c.grade.name
                ).select_related('subject')
                
                # Get total students in this class for percentage calculation
                total_students_in_class = StudentProfile.objects.filter(class_id=c).count()
                
                subjects_with_progress = []
                for conf in configs:
                    # Calculate progress: (Actual scores) / (Total expected scores)
                    # Total expected = students * papers
                    expected = total_students_in_class * conf.paper_count
                    if expected > 0:
                        actual = ExamSUbjectScore.objects.filter(
                            paper__exam_subject=conf,
                            student__studentprofile__class_id=c
                        ).count()
                        progress = round((actual / expected) * 100, 1)
                    else:
                        progress = 0
                    
                    subjects_with_progress.append({
                        'subject': conf.subject,
                        'progress': progress,
                        'is_complete': progress >= 100
                    })
                
                subjects_with_progress.sort(key=lambda x: x['subject'].name)
                
                if subjects_with_progress:
                    invigilated_data.append({
                        'class_obj': c,
                        'subjects': subjects_with_progress
                    })
        context['invigilated_data'] = invigilated_data

        # Get exams
        context['latest_exam'] = Exam.objects.order_by('-id').first()
        
        return context


class StudentsListView(LoginRequiredMixin, ListView):
    model = Student
    template_name = 'core/students_list.html'
    context_object_name = 'students'
    paginate_by = 100
    
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
        
        # Filter by school if user is linked to one and is not a superuser
        if not self.request.user.is_superuser and self.request.user.school:
            queryset = queryset.filter(studentprofile__school=self.request.user.school)
        
        # Filter by school if specified (and allowed)
        school_id = self.request.GET.get('school')
        if school_id:
            # If user is linked to a school, ignore requested school_id if it's different
            if not self.request.user.is_superuser and self.request.user.school:
                school_id = self.request.user.school.id
            queryset = queryset.filter(studentprofile__school_id=school_id)
            
        # Filter by grade (class) if specified
        grade_id = self.request.GET.get('grade')
        if grade_id:
            queryset = queryset.filter(studentprofile__class_id__grade_id=grade_id)
        
        # Filter by class (stream) if specified
        class_id = self.request.GET.get('class')
        if class_id:
            queryset = queryset.filter(studentprofile__class_id_id=class_id)
            
        # Date joined range filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(joined_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(joined_date__lte=date_to)
        
        # Status Filter (Active by default)
        status = self.request.GET.get('status', 'Active')
        if status:
            queryset = queryset.filter(studentprofile__status=status)
        
        return queryset.select_related('studentprofile__school', 'studentprofile__class_id', 'studentprofile__class_id__grade')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['search_query'] = self.request.GET.get('q', '')
        
        if not user.is_superuser and user.school:
            context['schools'] = School.objects.filter(id=user.school.id)
            context['selected_school'] = str(user.school.id)
        else:
            context['schools'] = School.objects.all()
            context['selected_school'] = self.request.GET.get('school', '')
        
        context['selected_class'] = self.request.GET.get('class', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        context['selected_status'] = self.request.GET.get('status', 'Active')
        
        # Use either the user's school or the selected school from GET
        selected_school_id = user.school.id if (not user.is_superuser and user.school) else self.request.GET.get('school')
        selected_grade_id = self.request.GET.get('grade')
        context['selected_grade'] = selected_grade_id
        
        if selected_school_id:
            from .models import Class, Grade
            from django.db.models import Q
            # Get grades that contextually belong to this school
            context['grades'] = Grade.objects.filter(Q(school_id=selected_school_id) | Q(school__isnull=True))
            
            if selected_grade_id:
                # Filter streams by grade AND school to ensure relevance
                context['classes'] = Class.objects.filter(grade_id=selected_grade_id, school_id=selected_school_id)
            else:
                # Show all streams for this school
                context['classes'] = Class.objects.filter(school_id=selected_school_id)
        else:
            context['grades'] = []
            context['classes'] = []
        
        context['total_students'] = self.get_queryset().count()
        return context


class StudentPromotionView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/student_promotion.html'

    def test_func(self):
        return self.request.user.role == 'Admin' or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        from .models import School, Class, StudentProfile, Grade, AcademicYear, PromotionHistory
        context = super().get_context_data(**kwargs)
        
        academic_years = AcademicYear.objects.all().order_by('-start_date')
        active_year = academic_years.filter(is_active=True).first()
        selected_year_id = self.request.GET.get('academic_year')
        
        # If no year selected, use active year
        if not selected_year_id and active_year:
            selected_year_id = str(active_year.id)
            
        context['academic_years'] = academic_years
        context['selected_year'] = selected_year_id
        context['active_year'] = active_year
        
        school_id = self.request.GET.get('school')
        class_id = self.request.GET.get('class')
        
        context['schools'] = School.objects.all()
        context['selected_school'] = school_id
        context['selected_class'] = class_id
        
        if school_id:
            context['classes'] = Class.objects.filter(school_id=school_id)
            context['target_classes'] = Class.objects.filter(school_id=school_id)
            
            if class_id:
                active_year = AcademicYear.objects.filter(is_active=True).first()
                context['active_year'] = active_year
                
                # 1. Get students currently in this class
                current_students = list(StudentProfile.objects.filter(
                    school_id=school_id, 
                    class_id_id=class_id,
                    status='Active'
                ).select_related('student'))
                
                # 2. Get students who were promoted INTO this class in the current year
                promoted_into_ids = []
                if active_year:
                    promoted_into_ids = list(PromotionHistory.objects.filter(
                        academic_year=active_year,
                        to_class_id=class_id
                    ).values_list('student_id', flat=True))

                # 3. Get students who were promoted FROM this class in the current year
                promoted_history = []
                if active_year:
                    promoted_history = PromotionHistory.objects.filter(
                        academic_year=active_year,
                        from_class_id=class_id
                    ).select_related('student', 'student__studentprofile', 'to_class')
                
                # Combine them for the view
                all_display_students = []
                processed_ids = set()
                
                # Add current students
                for p in current_students:
                    p.already_promoted = False
                    p.just_promoted = p.student_id in promoted_into_ids
                    all_display_students.append(p)
                    processed_ids.add(p.student_id)
                
                # Add students who were moved away (so they don't just disappear)
                for history in promoted_history:
                    if history.student_id not in processed_ids:
                        # Create a mock profile object for display
                        try:
                            profile = history.student.studentprofile
                        except:
                            continue
                        
                        profile.already_promoted = True
                        profile.promoted_to_name = history.to_class.name if history.to_class else "Graduated"
                        all_display_students.append(profile)
                        processed_ids.add(history.student_id)
                
                context['students'] = all_display_students
                
                # Identify next grade logic
                current_class = Class.objects.get(id=class_id)
                current_grade_name = current_class.grade.name
                
                grade_sequence = [g[0] for g in Grade.choices]
                try:
                    current_idx = grade_sequence.index(current_grade_name)
                    if current_idx < len(grade_sequence) - 1:
                        context['next_grade_name'] = grade_sequence[current_idx + 1]
                        context['suggested_classes'] = Class.objects.filter(
                            school_id=school_id,
                            grade__name=context['next_grade_name']
                        )
                    else:
                        context['is_final_grade'] = True
                except ValueError:
                    pass

            # Promotion Summary Section Logic
            summary = []
            school_classes = Class.objects.filter(school_id=school_id).select_related('grade')
            
            # Get all students promoted OUT of any class this year
            all_promoted_out = []
            if selected_year_id:
                all_promoted_out = list(PromotionHistory.objects.filter(
                    academic_year_id=selected_year_id,
                    from_class__isnull=False
                ).values_list('student_id', flat=True))

            # Get all students promoted INTO any class this year
            all_promoted_into = []
            if selected_year_id:
                all_promoted_into = list(PromotionHistory.objects.filter(
                    academic_year_id=selected_year_id,
                    to_class__isnull=False
                ).values_list('student_id', flat=True))

            for c in school_classes:
                # 1. Total active currently in class
                total_active = StudentProfile.objects.filter(class_id=c, status='Active').count()
                
                # 2. How many of these were just promoted INTO here? 
                # Crucial: Only count those STILL in this class.
                just_arrived = StudentProfile.objects.filter(
                    class_id=c, 
                    status='Active',
                    student_id__in=all_promoted_into
                ).count()
                
                # 3. How many have we moved OUT of here?
                promoted_away = 0
                if selected_year_id:
                    promoted_away = PromotionHistory.objects.filter(
                        academic_year_id=selected_year_id,
                        from_class=c
                    ).count()
                
                # The 'Original Total' for this class is:
                # (Students who started the year here and haven't moved yet) + (Students who were here and moved out)
                # Original Still Here = Current Active - Arrivals from elsewhere
                remaining = max(0, total_active - just_arrived)
                real_total = remaining + promoted_away
                
                percentage = 0.0
                if real_total > 0:
                    percentage = round((float(promoted_away) / float(real_total)) * 100, 1)
                
                # Reshuffling points: PP2 -> Grade 1, Grade 6 -> Grade 7
                is_reshuffling_grade = c.grade.name in ['PP2', 'Grade 6']
                
                summary.append({
                    'class_name': f"{c.grade.name} {c.name}",
                    'promoted': promoted_away,
                    'remaining': remaining,
                    'total': real_total,
                    'percentage': min(100.0, percentage),
                    'is_complete': real_total > 0 and remaining == 0,
                    'needs_shuffling': is_reshuffling_grade,
                })
            
            context['promotion_summary'] = summary
                    
        return context

    def post(self, request, *args, **kwargs):
        student_ids = request.POST.getlist('student_ids')
        action = request.POST.get('action')
        target_class_id = request.POST.get('target_class')
        
        if not student_ids:
            messages.warning(request, 'No students selected.')
            return redirect(request.get_full_path())
            
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if not active_year:
            messages.error(request, 'No active academic year found. Please activate an academic year first.')
            return redirect(request.get_full_path())
        
        active_term = Term.objects.filter(is_active=True).first()
        
        # Pre-fetch fee structures for the active term to avoid N+1 queries
        fee_map = {}
        if active_term:
            f_structures = FeeStructure.objects.filter(term=active_term).prefetch_related('grade')
            for fs in f_structures:
                for grade in fs.grade.all():
                    fee_map[(fs.school_id, grade.id, fs.student_type)] = fs
        
        profiles = StudentProfile.objects.filter(student_id__in=student_ids).select_related('student', 'school')
        success_count = 0
        invoice_count = 0
        
        for profile in profiles:
            old_class = profile.class_id
            
            if action == 'promote' and target_class_id:
                target_class = Class.objects.get(id=target_class_id)
                profile.class_id = target_class
                profile.save()
                
                # Log History
                PromotionHistory.objects.create(
                    student=profile.student,
                    from_class=old_class,
                    to_class=target_class,
                    academic_year=active_year
                )
                success_count += 1
                
                # Invoicing Logic
                if active_term:
                    fee_type = profile.student.get_fee_student_type()
                    fs = fee_map.get((profile.school_id, target_class.grade_id, fee_type))
                    
                    if fs:
                        # Guard against duplicate invoicing for the same fee structure and calendar year
                        target_cal_year = active_year.start_date.year
                        if not Invoice.objects.filter(student=profile.student, fee_structure=fs, created_at__year=target_cal_year).exists():
                            multiplier = profile.student.get_fee_multiplier()
                            final_amount = fs.amount * Decimal(str(multiplier))
                            
                            Invoice.objects.create(
                                student=profile.student,
                                fee_structure=fs,
                                amount=final_amount,
                                description=f'First Term Fees - Academic Year {active_year}'
                            )
                            invoice_count += 1
                
            elif action == 'graduate':
                profile.status = 'Graduated'
                profile.class_id = None
                profile.save()
                
                # Log History
                PromotionHistory.objects.create(
                    student=profile.student,
                    from_class=old_class,
                    academic_year=active_year,
                    is_graduation=True
                )
                success_count += 1
        
        if success_count > 0:
            msg = f'Successfully processed {success_count} students.'
            if invoice_count > 0:
                msg += f' {invoice_count} invoices generated.'
            messages.success(request, msg)
        else:
            messages.error(request, 'Invalid action or target class selected.')
            
        return redirect(request.get_full_path())


class GuardianListView(LoginRequiredMixin, ListView):
    from users.models import MyUser
    model = MyUser
    template_name = 'core/guardian_list.html'
    context_object_name = 'guardians'
    paginate_by = 20
    
    def get_queryset(self):
        from users.models import MyUser
        queryset = MyUser.objects.filter(role='Guardian').order_by('first_name', 'last_name')
        
        # Get search query
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query) | 
                Q(email__icontains=query)
            )
            
        return queryset.prefetch_related('students')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['total_guardians'] = self.get_queryset().count()
        return context


def create_student(request):
    if request.method == 'POST':
        student_form = StudentForm(request.POST)
        profile_form = StudentProfileForm(request.POST)
        
        if student_form.is_valid() and profile_form.is_valid():
            student = student_form.save(commit=False)
            # keep legacy boolean in sync for existing logic
            student.is_boarder = student.get_fee_student_type() == 'boarder'
            student.save()
            profile = profile_form.save(commit=False)
            
            # Use the balance from the form as the initial invoice amount
            # But set the profile balance to 0 first to avoid doubling it 
            # when the Invoice.save() updates the profile.
            initial_balance = profile.fee_balance
            profile.fee_balance = 0
            profile.student = student
            profile.save()

            # Auto-generate admission number: E{first letter of second name of school name}-student.id
            if profile.school:
                name_parts = profile.school.name.split()
                # Get first letter of second word if it exists
                initial = name_parts[1][0].upper() if len(name_parts) > 1 else ""
                student.adm_no = f"E{initial}-{student.id}"
                student.save()

            # Negotiated admission fee (invoiced as agreed amount)
            from accounts.models import AdmissionFee, Invoice
            admission_fee_raw = request.POST.get('admission_fee_amount', '').strip()
            if admission_fee_raw:
                try:
                    agreed_admission_fee = int(float(admission_fee_raw))
                except ValueError:
                    agreed_admission_fee = 0
            else:
                agreed_admission_fee = 0

            if agreed_admission_fee > 0:
                Invoice.objects.create(
                    student=student,
                    amount=agreed_admission_fee,
                    description="Admission Fee",
                )

            # Auto-invoice current term fee based on configured fee structure
            from accounts.models import FeeStructure
            from core.models import Term
            from decimal import Decimal
            from django.db.models import Q
            active_term = Term.objects.filter(is_active=True).first()
            if not active_term:
                messages.warning(request, "No active term is set. Term fees were not invoiced on enrollment.")
            elif not profile.class_id:
                messages.warning(request, "No class was selected. Term fees were not invoiced on enrollment.")
            else:
                student_type = student.get_fee_student_type()  # 'day' or 'boarder'
                fee_structure = FeeStructure.objects.filter(
                    term=active_term,
                    student_type=student_type,
                    grade=profile.class_id.grade,
                ).filter(
                    Q(school=profile.school) | Q(school__isnull=True)
                ).order_by('-school').first()

                if fee_structure:
                    multiplier = Decimal(str(student.get_fee_multiplier()))
                    term_amount = (Decimal(str(fee_structure.amount)) * multiplier).quantize(Decimal('1.00'))
                    if term_amount > 0 and not Invoice.objects.filter(student=student, fee_structure=fee_structure).exists():
                        Invoice.objects.create(
                            student=student,
                            fee_structure=fee_structure,
                            amount=term_amount,
                        )
                else:
                    messages.warning(
                        request,
                        "No fee structure found for the selected school/grade/type in the active term. Term fees were not invoiced."
                    )

            # Optional additional charges at enrollment (full amounts; no staff discount)
            from accounts.models import AdditionalCharges
            charge_ids = request.POST.getlist('additional_charge_ids')
            if charge_ids:
                charges = AdditionalCharges.objects.filter(
                    id__in=charge_ids,
                    school=profile.school,
                    grades=profile.class_id.grade if profile.class_id else None,
                ).distinct()
                for ch in charges:
                    Invoice.objects.create(
                        student=student,
                        amount=ch.amount,
                        description=f"Additional Charge: {ch.name}",
                    )

            # 4. Calculate Adjustment vs the "Opening Balance" target the user entered in the form
            # Because the Term/Admission/Additional invoices created above INCREASE the profile balance (due to Invoice.save),
            # we need to create an "Adjustment" invoice for whatever is left over from initial_balance.
            total_auto_invoiced = 0
            # Total up what we've actually invoiced above in this one code block
            # Admission
            total_auto_invoiced += agreed_admission_fee
            # Term Fee (term_amount was defined in the block above)
            try:
                if 'term_amount' in locals() and term_amount > 0:
                    total_auto_invoiced += int(term_amount)
            except NameError:
                pass
            
            # Additional Charges
            if charge_ids:
                total_auto_invoiced += sum(int(ch.amount) for ch in charges)

            # The final Adjustment (could be + arrears or - discount)
            adjustment = initial_balance - total_auto_invoiced
            
            if adjustment != 0:
                Invoice.objects.create(
                    student=student,
                    amount=adjustment,
                    description="Opening Balance Adjustment / Arrears",
                    is_billed=(adjustment > 0)
                )

            messages.success(request, f'Student {student.first_name} {student.last_name} has been enrolled successfully!')
            return redirect('core:student-detail', pk=student.pk)
    else:
        student_form = StudentForm()
        profile_form = StudentProfileForm()
    
    from accounts.models import AdditionalCharges, AdmissionFee
    default_admission_fee = AdmissionFee.objects.order_by('-created_at').first()
    try:
        admission_fee_default = int(default_admission_fee.amount) if default_admission_fee else 0
    except Exception:
        admission_fee_default = 0
    admission_fee_max = admission_fee_default if admission_fee_default > 0 else 50000
    context = {
        'student_form': student_form,
        'profile_form': profile_form,
        'additional_charges': AdditionalCharges.objects.select_related('school').all(),
        'default_admission_fee': default_admission_fee,
        'admission_fee_default': admission_fee_default,
        'admission_fee_max': admission_fee_max,
    }
    return render(request, 'core/create_student.html', context)


@login_required
def get_school_classes(request):
    school_id = request.GET.get('school_id')
    if not school_id:
        return JsonResponse({'classes': []})
    
    classes = Class.objects.filter(school_id=school_id).select_related('grade')
    data = [
        {'id': c.id, 'name': f"{c.name} ({c.grade.name})"} 
        for c in classes
    ]
    return JsonResponse({'classes': data})

@login_required
def fee_structure_preview(request):
    """
    Live preview for enrollment page: returns the term fee that will be invoiced
    for a selected school + class + fee category, using the active term.
    """
    from accounts.models import FeeStructure
    from core.models import Term, Class as SchoolClass
    from django.db.models import Q
    from decimal import Decimal

    school_id = request.GET.get('school_id')
    class_id = request.GET.get('class_id')
    fee_category = request.GET.get('fee_category', 'day')

    if not school_id or not class_id:
        return JsonResponse({'found': False, 'reason': 'Missing school/class'}, status=400)

    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        return JsonResponse({'found': False, 'reason': 'No active term set'}, status=200)

    try:
        class_obj = SchoolClass.objects.select_related('grade').get(id=class_id, school_id=school_id)
    except SchoolClass.DoesNotExist:
        return JsonResponse({'found': False, 'reason': 'Class not found for school'}, status=200)

    student_type = 'boarder' if fee_category in ('boarder', 'staff_boarder') else 'day'
    multiplier = Decimal('0.5') if fee_category in ('staff_boarder', 'staff_day') else (Decimal('0') if fee_category == 'director' else Decimal('1'))

    fs = FeeStructure.objects.filter(
        term=active_term,
        student_type=student_type,
        grade=class_obj.grade,
    ).filter(Q(school_id=school_id) | Q(school__isnull=True)).order_by('-school').first()

    if not fs:
        return JsonResponse({'found': False, 'reason': 'No matching fee structure'}, status=200)

    amount = (Decimal(str(fs.amount)) * multiplier).quantize(Decimal('1.00'))
    return JsonResponse({
        'found': True,
        'term': active_term.name,
        'student_type': student_type,
        'fee_structure_id': fs.id,
        'base_amount': str(fs.amount),
        'multiplier': str(multiplier),
        'amount': str(amount),
    })

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
        # Fetch all available exams for the filter dropdown (newest first)
        # Fetch all available exams for the filter dropdown (newest first)
        context['all_exams'] = Exam.objects.all().order_by('-id')
        
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
        
        # Fetch detailed profile and guardians
        context['profile'] = StudentProfile.objects.filter(student=self.object).first()
        context['guardians'] = self.object.guardians.all()
        
        # Fetch filtered exam scores with aggregation by subject
        if selected_exam:
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
                        # Fallback logic for Junior Secondary
                        is_jss = self.object.studentprofile.class_id.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if hasattr(self.object, 'studentprofile') and self.object.studentprofile and self.object.studentprofile.class_id.grade else False
                        if is_jss:
                            if perc >= 90: grade = 'EE1'
                            elif perc >= 80: grade = 'EE2'
                            elif perc >= 70: grade = 'ME1'
                            elif perc >= 60: grade = 'ME2'
                            elif perc >= 50: grade = 'AE1'
                            elif perc >= 40: grade = 'AE2'
                            elif perc >= 20: grade = 'BE1'
                            else: grade = 'BE2'
                        else:
                            if perc >= 70: grade = 'EE'
                            elif perc >= 60: grade = 'ME'
                            elif perc >= 50: grade = 'AE'
                else:
                    # Fallback logic for Junior Secondary
                    is_jss = self.object.studentprofile.class_id.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if hasattr(self.object, 'studentprofile') and self.object.studentprofile and self.object.studentprofile.class_id.grade else False
                    if is_jss:
                        if perc >= 90: grade = 'EE1'
                        elif perc >= 80: grade = 'EE2'
                        elif perc >= 70: grade = 'ME1'
                        elif perc >= 60: grade = 'ME2'
                        elif perc >= 50: grade = 'AE1'
                        elif perc >= 40: grade = 'AE2'
                        elif perc >= 20: grade = 'BE1'
                        else: grade = 'BE2'
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
                
                # Calculate Points (8-point scale for JSS, 4-point for others)
                point_map = {
                    'EE1': 8, 'EE2': 7, 
                    'ME1': 6, 'ME2': 5, 
                    'AE1': 4, 'AE2': 3, 
                    'BE1': 2, 'BE2': 1,
                    'EE': 4, 'ME': 3, 'AE': 2, 'BE': 1
                }
                points = point_map.get(grade, 1)

                # Map back to namespace for template access (score.subject.name)
                scores.append(SimpleNamespace(
                    subject=data['subject'],
                    score=data['total_score'],
                    max_score=data['max_score'],
                    percentage=round(perc, 1),
                    grade=grade,
                    points=points,
                    score_diff=score_diff,
                    abs_score_diff=abs_score_diff
                ))

        else:
            scores = []
            
        context['exam_scores'] = scores
        
        # Fetch payment history
        # Fetch financial log (Payments + Invoices)
        from accounts.models import Payment, Invoice
        student_payments = Payment.objects.filter(student=self.object)
        student_invoices = Invoice.objects.filter(student=self.object)
        context['total_paid'] = student_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        from core.models import StudentDiscipline, AcademicYear, Term
        from transport.models import TransportAssignment
        context['discipline_records'] = StudentDiscipline.objects.filter(student=self.object)
        
        # Get active transport assignment for current period
        active_year = AcademicYear.objects.filter(is_active=True).first()
        active_term = Term.objects.filter(is_active=True).first()
        context['active_transport'] = TransportAssignment.objects.filter(
            student=self.object,
            academic_year=active_year,
            term=active_term,
            is_active=True
        ).select_related('route', 'vehicle').first()
        
        financial_log = []
        for p in student_payments:
            financial_log.append({
                'type': 'payment',
                'description': 'Fee Payment',
                'amount': p.amount,
                'date': p.date_paid, # Keep for display
                'sort_date': p.created_at if hasattr(p, 'created_at') else timezone.now(), # Use timestamp for sort
                'method': getattr(p, 'method', None),
                'balance_before': p.previous_balance,
                'balance_after': p.current_balance
            })
        for i in student_invoices:
            if i.fee_structure:
                # FeeStructure doesn't have academic_year; use invoice date
                year = i.created_at.year if i.created_at else ""
                desc = f"Billed: {i.fee_structure.term.name} {year}"
            else:
                desc = i.description or "General Billing"
                
            financial_log.append({
                'type': 'invoice',
                'description': desc,
                'amount': i.amount,
                'date': i.created_at.date() if hasattr(i, 'created_at') else timezone.now().date(),
                'sort_date': i.created_at if hasattr(i, 'created_at') else timezone.now(),
                'balance_before': i.previous_balance,
                'balance_after': i.current_balance
            })
            
        financial_log.sort(key=lambda x: x['sort_date'], reverse=True)
        context['financial_log'] = financial_log[:15]
        context['payments'] = student_payments.order_by('-date_paid')
        
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
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'assign_invigilator':
            # Only superusers, admins, and exam officers can assign invigilators
            if not request.user.is_superuser and not (hasattr(request.user, 'role') and request.user.role == 'Admin' or request.user.is_exam_officer):
                from django.contrib import messages
                messages.error(request, "Only administrators and exam officers can assign invigilators.")
                return redirect('core:classes-list')
                
            class_id = request.POST.get('class_id')
            teacher_id = request.POST.get('teacher_id')
            
            if class_id and teacher_id:
                try:
                    from .models import Class
                    from users.models import MyUser
                    from django.contrib import messages
                    
                    class_obj = Class.objects.get(id=class_id)
                    teacher = MyUser.objects.get(id=teacher_id)
                    
                    class_obj.invigilator = teacher
                    class_obj.save()
                    
                    messages.success(request, f"Invigilator {teacher.get_full_name() or teacher.email} assigned to {class_obj.name}.")
                except Exception as e:
                    from django.contrib import messages
                    messages.error(request, f"Error assigning invigilator: {str(e)}")
                    
        elif action == 'assign_class_teacher':
            # Only superusers, admins, and head teachers can assign class teachers
            if not request.user.is_superuser and not (hasattr(request.user, 'role') and request.user.role == 'Admin' or request.user.is_headteacher):
                from django.contrib import messages
                messages.error(request, "Only administrators and head teachers can assign class teachers.")
                return redirect('core:classes-list')
                
            class_id = request.POST.get('class_id')
            teacher_id = request.POST.get('teacher_id')
            
            if class_id and teacher_id:
                try:
                    from .models import Class
                    from users.models import MyUser
                    from django.contrib import messages
                    
                    class_obj = Class.objects.get(id=class_id)
                    teacher = MyUser.objects.get(id=teacher_id)
                    
                    class_obj.class_teacher = teacher
                    class_obj.save()
                    
                    messages.success(request, f"Class teacher {teacher.get_full_name() or teacher.email} assigned to {class_obj.name}.")
                except Exception as e:
                    from django.contrib import messages
                    messages.error(request, f"Error assigning class teacher: {str(e)}")
                    
        return redirect('core:classes-list')
    
    def get_queryset(self):
        queryset = Class.objects.all().select_related('grade', 'grade__school')
        
        # Filter by school if user is linked to one
        if self.request.user.school:
            queryset = queryset.filter(grade__school=self.request.user.school)
        elif not self.request.user.is_superuser:
            # Non-admins without a linked school might see nothing or get an error
            # For now, let's keep them scoped to empty if no school is found
            queryset = queryset.none()
        
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
        elif self.request.user.school:
            # Filter grades by user's linked school
            context['grades'] = Grade.objects.filter(school=self.request.user.school)
        else:
            context['grades'] = []
        
        context['selected_grade'] = self.request.GET.get('grade', '')
        
        # --- Real stats for cards ---
        queryset = self.get_queryset()
        context['total_classes'] = queryset.count()
        
        # Total Enrollments (Active Students)
        context['total_enrollments'] = StudentProfile.objects.filter(
            class_id__in=queryset,
            status='Active'
        ).count()
        
        # Total Teachers assigned to these classes
        teacher_ids = set()
        teacher_ids.update(queryset.filter(invigilator__isnull=False).values_list('invigilator_id', flat=True))
        teacher_ids.update(queryset.filter(class_teacher__isnull=False).values_list('class_teacher_id', flat=True))
        teacher_ids.update(TeacherClassProfile.objects.filter(class_id__in=queryset).values_list('user_id', flat=True))
        context['total_teachers_count'] = len(teacher_ids)
        
        # Total Campuses
        if self.request.user.is_superuser:
            context['total_campuses'] = School.objects.count()
        else:
            context['total_campuses'] = 1

        # Capacity Stats for Donut Chart (Under < 15, Optimal 15-35, Over > 35)
        under_count = 0
        optimal_count = 0
        over_count = 0
        
        for c in queryset.annotate(count=Count('studentprofile', filter=Q(studentprofile__status='Active'))):
            if c.count < 15:
                under_count += 1
            elif c.count <= 35:
                optimal_count += 1
            else:
                over_count += 1
        
        context['capacity_under'] = under_count
        context['capacity_optimal'] = optimal_count
        context['capacity_over'] = over_count

        # --- Real Daily Attendance Data (School-wide) ---
        today = timezone.now().date()
        start_date = today - timedelta(days=15)
        
        # Get sessions in range, scoped to school if needed
        att_sessions = AttendanceSession.objects.filter(date__gte=start_date, date__lte=today)
        if not self.request.user.is_superuser:
            try:
                user_school = self.request.user.profile.school
                att_sessions = att_sessions.filter(class_id__grade__school=user_school)
            except AttributeError:
                pass
        
        # Aggregate by day
        daily_stats = (
            StudentAttendance.objects.filter(session__in=att_sessions)
            .values('session__date')
            .annotate(
                present=Count('id', filter=Q(status='Present')),
                absent=Count('id', filter=Q(status='Absent')),
                late=Count('id', filter=Q(status='Late')),
                half_day=Count('id', filter=Q(status='Half Day'))
            ).order_by('session__date')
        )
        
        # Map stats by date
        stats_by_date = {s['session__date']: s for s in daily_stats}
        
        att_labels = []
        att_present = []
        att_absent = []
        att_late = []
        
        # Fill in labels and data, including empty days
        curr = start_date
        while curr <= today:
            label = curr.strftime('%d %b')
            att_labels.append(label)
            
            day_data = stats_by_date.get(curr, {})
            att_present.append(day_data.get('present', 0))
            att_absent.append(day_data.get('absent', 0))
            att_late.append(day_data.get('late', 0) + day_data.get('half_day', 0))
            
            curr += timedelta(days=1)
            
        context['school_attendance_labels'] = json.dumps(att_labels)
        context['school_attendance_present'] = json.dumps(att_present)
        context['school_attendance_absent'] = json.dumps(att_absent)
        context['school_attendance_late'] = json.dumps(att_late)
        # --- End Attendance Data ---

        from users.models import MyUser
        context['teachers'] = MyUser.objects.filter(role='Teacher', is_active=True).order_by('first_name', 'last_name')
        
        return context


class ClassDetailView(LoginRequiredMixin, DetailView):
    model = Class
    template_name = 'core/class_detail.html'
    context_object_name = 'class_obj'

    def post(self, request, *args, **kwargs):
        class_obj = self.get_object()
        if not request.user.is_superuser and not (hasattr(request.user, 'role') and request.user.role == 'Admin') and request.user != class_obj.class_teacher:
            messages.error(request, "Only administrators and class teachers can assign teachers.")
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
        from users.models import MyUser

        context['teacher_assignments'] = TeacherClassProfile.objects.filter(
            user=self.request.user, 
            class_id=self.object
        ).select_related('subject')
        
        # Determine active exam: BOTH is_running AND ExamMode active must be true
        from core.models import ExamMode
        
        # Determine active exam: prioritize ExamMode, fall back to latest running exam
        # Get the singleton ExamMode
        exam_mode = ExamMode.objects.select_related('exam').first()
        
        # Active exam = ExamMode points to an exam that also has is_running=True
        active_exam = None
        if exam_mode and exam_mode.active and exam_mode.exam and exam_mode.exam.is_running:
            active_exam = exam_mode.exam
            
        if not active_exam:
            # Fallback to latest running exam if no ExamMode is active
            active_exam = Exam.objects.filter(is_running=True).order_by('-id').first()
        
        context['active_exam'] = active_exam
        context['latest_exam'] = Exam.objects.order_by('-id').first()

        # Admin/Class Teacher View: Manage Teachers
        if self.request.user.is_superuser or (hasattr(self.request.user, 'role') and self.request.user.role == 'Admin') or self.request.user == self.object.class_teacher:
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
        
        # We'll reverse recent_attendance for chronological chart plotting
        # Convert to list first to avoid slicing/reversing issues with querysets
        sessions_list = list(recent_attendance)
        
        for session in reversed(sessions_list):
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
        'exam_modes': ExamMode.objects.all(),
        'schools': School.objects.all(),
        'fee_structures': FeeStructure.objects.all().select_related('term').prefetch_related('grade'),
    }
    
    # Get forms for each model
    context['academic_year_form'] = AcademicYearForm()
    context['term_form'] = TermForm()
    context['grade_form'] = GradeForm()
    context['class_form'] = ClassForm()
    context['exam_form'] = ExamForm()
    context['exam_mode_form'] = ExamModeForm()
    
    from accounts.forms import FeeStructureForm, AdditionalChargesForm
    from accounts.models import AdditionalCharges
    context['fee_structure_form'] = FeeStructureForm()
    context['additional_charge_form'] = AdditionalChargesForm()
    context['additional_charges'] = AdditionalCharges.objects.all().select_related('school').prefetch_related('grades')
    
    return render(request, 'core/configurations.html', context)

def create_fee_structure(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'Permission denied.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        from accounts.forms import FeeStructureForm
        form = FeeStructureForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee structure created successfully!')
        else:
            messages.error(request, 'Error creating fee structure.')
            
    return redirect('core:configurations')


def create_additional_charge(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'Permission denied.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        from accounts.forms import AdditionalChargesForm
        form = AdditionalChargesForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Additional charge created successfully!')
        else:
            messages.error(request, 'Error creating additional charge.')
            
    return redirect('core:configurations')



def activate_academic_year(request, year_id):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'Permission denied.')
        return redirect('core:configurations')
    
    # Deactivate all others
    AcademicYear.objects.all().update(is_active=False)
    # Activate the selected one
    year = get_object_or_404(AcademicYear, id=year_id)
    year.is_active = True
    year.save()
    messages.success(request, f'Academic year {year.start_date.year} is now active.')
    return redirect('core:configurations')

def activate_term(request, term_id):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'Permission denied.')
        return redirect('core:configurations')
    
    # Deactivate all others
    Term.objects.all().update(is_active=False)
    # Activate the selected one
    term = get_object_or_404(Term, id=term_id)
    term.is_active = True
    term.save()
    messages.success(request, f'Term {term.name} is now active.')
    return redirect('core:configurations')

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


def update_term(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        term = get_object_or_404(Term, id=term_id)
        form = TermForm(request.POST, instance=term)
        if form.is_valid():
            form.save()
            messages.success(request, 'Term updated successfully!')
        else:
            messages.error(request, 'Failed to update term. Please check your data.')
            
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


def update_class(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        class_obj = get_object_or_404(Class, id=class_id)
        
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class updated successfully!')
        else:
            messages.error(request, f'Error updating class: {form.errors}')
    
    return redirect('core:configurations')


def create_exam(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('core:configurations')
    
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.created_by = request.user
            exam.updated_by = request.user
            exam.save()
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
            messages.success(request, f'Exam mode updated successfully!')
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
            item_name = str(item)
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
        elif model_type == 'fee_structure':
            item = get_object_or_404(FeeStructure, id=item_id)
            item.delete()
            messages.success(request, 'Fee structure deleted successfully!')
        elif model_type == 'additional_charge':
            from accounts.models import AdditionalCharges
            item = get_object_or_404(AdditionalCharges, id=item_id)
            item.delete()
            messages.success(request, 'Additional charge deleted successfully!')
        elif model_type == 'exam_mode':
            messages.warning(request, 'Exam mode cannot be deleted. Use the exam management page to activate/deactivate exams.')
    
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

    # Sanitize & Default to latest exam if none provided
    if selected_exam is None:
        latest_exam = exams.first()
        selected_exam = str(latest_exam.id) if latest_exam else None
    elif selected_exam in ['None', '']:
        selected_exam = None
    
    if selected_subject in ['None', '', None]: selected_subject = None
    
    # Ensure selected_exam is a digit if provided
    if selected_exam and not str(selected_exam).isdigit():
        selected_exam = None
    
    # Apply filters
    if selected_exam:
        exam_scores = exam_scores.filter(paper__exam_subject__exam_id=selected_exam)
    if selected_subject:
        exam_scores = exam_scores.filter(paper__exam_subject__subject_id=selected_subject)
        
    # NEW: Fetch rankings if we have a specific subject filter
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
        
        # Fallback logic for Grade 7/8/9
        is_junior_secondary = student_grade_name in ['Grade 7', 'Grade 8', 'Grade 9']
        if is_junior_secondary:
            if score >= 90: return 'EE1'
            if score >= 80: return 'EE2'
            if score >= 70: return 'ME1'
            if score >= 60: return 'ME2'
            if score >= 50: return 'AE1'
            if score >= 40: return 'AE2'
            if score >= 20: return 'BE1'
            return 'BE2'
            
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
                is_junior_secondary = class_obj.grade.name in ['Grade 7', 'Grade 8', 'Grade 9']
                if is_junior_secondary:
                    if perc >= 90: best_grade = 'EE1'
                    elif perc >= 80: best_grade = 'EE2'
                    elif perc >= 70: best_grade = 'ME1'
                    elif perc >= 60: best_grade = 'ME2'
                    elif perc >= 50: best_grade = 'AE1'
                    elif perc >= 40: best_grade = 'AE2'
                    elif perc >= 20: best_grade = 'BE1'
                    else: best_grade = 'BE2'
                else:
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

    # Dynamically determine the grade list for charts and tallies
    is_junior_secondary = class_obj.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if class_obj.grade else False
    if is_junior_secondary:
        current_grade_list = ['EE1', 'EE2', 'ME1', 'ME2', 'AE1', 'AE2', 'BE1', 'BE2']
    else:
        current_grade_list = ['EE', 'ME', 'AE', 'BE']

    grade_counts = {g: 0 for g in current_grade_list}
    for s in ranked_students:
        avg = s['avg_score']
        g = get_score_grade(avg, class_obj.grade.name)
        if g in grade_counts:
            grade_counts[g] += 1
    # Calculate aggregated counts for summary cards
    level_counts = {
        'EE': grade_counts.get('EE', 0) + grade_counts.get('EE1', 0) + grade_counts.get('EE2', 0),
        'ME': grade_counts.get('ME', 0) + grade_counts.get('ME1', 0) + grade_counts.get('ME2', 0),
        'AE': grade_counts.get('AE', 0) + grade_counts.get('AE1', 0) + grade_counts.get('AE2', 0),
        'BE': grade_counts.get('BE', 0) + grade_counts.get('BE1', 0) + grade_counts.get('BE2', 0),
    }

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
        'is_junior_secondary': is_junior_secondary,
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
    
    context['grade_labels_js'] = json.dumps(current_grade_list)
    context['grade_data_js'] = json.dumps([grade_counts.get(g, 0) for g in current_grade_list])
    
    # Gender Distribution by Grade for Grouped Bar Chart
    gender_grade_data = {
        'male': {g: 0 for g in current_grade_list},
        'female': {g: 0 for g in current_grade_list}
    }
    for s in ranked_students:
        gen = s['student'].gender
        sc = s['avg_score']
        g = get_score_grade(sc, class_obj.grade.name)
        if gen in gender_grade_data:
            gender_grade_data[gen][g] += 1
            
    context['gender_labels_js'] = json.dumps(current_grade_list)
    context['gender_male_data_js'] = json.dumps([gender_grade_data.get('male', {}).get(g, 0) for g in current_grade_list])
    context['gender_female_data_js'] = json.dumps([gender_grade_data.get('female', {}).get(g, 0) for g in current_grade_list])
    
    return render(request, 'core/class_exam_analytics.html', context)


@login_required
def class_merit_list(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Get all students in this class
    students = StudentProfile.objects.filter(class_id=class_id).select_related('student')
    
    # Get all exam scores for students in this class
    exam_scores = ExamSUbjectScore.objects.filter(
        student__in=[sp.student for sp in students]
    ).select_related('student', 'paper__exam_subject__subject', 'paper__exam_subject__exam').order_by('paper__exam_subject__exam', 'paper__exam_subject__subject')
    
    # Get filter parameters
    selected_exam = request.GET.get('exam')
    selected_subject = request.GET.get('subject')
    
    # Get available exams for defaulting
    exams = Exam.objects.all().select_related('year', 'term').order_by('-year__start_date', 'term__name')

    # Sanitize & Default to latest exam if none provided
    if selected_exam is None:
        latest_exam = exams.first()
        selected_exam = str(latest_exam.id) if latest_exam else None
    elif selected_exam in ['None', '']:
        selected_exam = None
    
    if selected_subject in ['None', '', None]: selected_subject = None
    
    # Apply filters with strict digit validation to prevent ValueErrors
    if selected_exam:
        if str(selected_exam).isdigit():
            exam_scores = exam_scores.filter(paper__exam_subject__exam_id=selected_exam)
        else:
            selected_exam = None
            
    if selected_subject:
        if str(selected_subject).isdigit():
            exam_scores = exam_scores.filter(paper__exam_subject__subject_id=selected_subject)
        else:
            selected_subject = None

    exam_obj = None
    if selected_exam:
        exam_obj = Exam.objects.filter(id=selected_exam).first()
        
    # NEW: Fetch rankings
    # Organize data for display
    analytics_data = {}
    
    # Get all subject configurations for this grade and exam context
    subject_configs = ExamSubjectConfiguration.objects.filter(
        subject__grade=class_obj.grade.name
    ).select_related('subject', 'exam')
    
    config_data_map = {}
    for config in subject_configs:
        config_data_map[(config.exam_id, config.subject_id)] = {
            'rankings': list(config.get_score_rankings()),
            'max_score': config.max_score or 100
        }

    def get_score_grade(score, student_grade_name, rankings=None):
        if rankings:
            for r in rankings:
                if r.min_score <= score <= r.max_score:
                    return r.grade
        
        # Fallback logic for Grade 7/8/9
        is_junior_secondary = student_grade_name in ['Grade 7', 'Grade 8', 'Grade 9']
        if is_junior_secondary:
            if score >= 90: return 'EE1'
            if score >= 80: return 'EE2'
            if score >= 70: return 'ME1'
            if score >= 60: return 'ME2'
            if score >= 50: return 'AE1'
            if score >= 40: return 'AE2'
            if score >= 20: return 'BE1'
            return 'BE2'
            
        if score >= 70: return 'EE'
        if score >= 60: return 'ME'
        if score >= 50: return 'AE'
        return 'BE'

    for student_profile in students:
        student = student_profile.student
        student_scores = exam_scores.filter(student=student)
        
        subject_scores = {}
        for score in student_scores:
            subject_obj = score.subject
            subject_name = subject_obj.name
            exam_obj_inner = score.exam
            
            if subject_name not in subject_scores:
                subject_scores[subject_name] = {
                    'score': 0,
                    'grade': '',
                    'percentage': 0,
                    'exam': exam_obj_inner.name,
                    'subject_id': subject_obj.id,
                    'exam_id': exam_obj_inner.id
                }
            subject_scores[subject_name]['score'] += score.score
            
        student_subject_percentages = []
        for s_name, s_data in subject_scores.items():
            s_total_score = s_data['score']
            conf = config_data_map.get((s_data['exam_id'], s_data['subject_id']), {})
            s_rankings = conf.get('rankings', [])
            s_max = conf.get('max_score', 100)
            
            perc = (s_total_score / s_max) * 100 if s_max > 0 else 0
            s_data['percentage'] = round(perc, 1)
            student_subject_percentages.append(perc)
            
            s_data['grade'] = get_score_grade(perc, class_obj.grade.name, s_rankings)

        total_score_sum = sum(s['score'] for s in subject_scores.values())
        avg_percentage = sum(student_subject_percentages) / len(student_subject_percentages) if student_subject_percentages else 0
        
        analytics_data[student.id] = {
            'student': student,
            'profile': student_profile,
            'total_score': total_score_sum,
            'avg_score': round(avg_percentage, 1),
            'subject_scores': subject_scores,
        }
    
    # Calculate rankings
    if selected_subject:
        subj_name_obj = Subject.objects.filter(id=selected_subject).first()
        subj_name = subj_name_obj.name if subj_name_obj else ""
        ranked_students = sorted(
            analytics_data.values(),
            key=lambda x: x['subject_scores'].get(subj_name, {}).get('score', 0),
            reverse=True
        )
    else:
        ranked_students = sorted(
            analytics_data.values(),
            key=lambda x: x['avg_score'],
            reverse=True
        )
    
    for rank, student_data in enumerate(ranked_students, 1):
        student_data['rank'] = rank
    
    # Subjects for table
    if selected_subject:
        table_subjects = [get_object_or_404(Subject, id=selected_subject)]
    else:
        grade_name = class_obj.grade.name
        table_subjects = list(Subject.objects.filter(grade=grade_name).order_by('name'))
        if not table_subjects:
            table_subjects = list(set(score.subject for score in exam_scores))
            table_subjects.sort(key=lambda x: x.name)

    for subject in table_subjects:
        if selected_exam:
            conf = ExamSubjectConfiguration.objects.filter(exam_id=selected_exam, subject=subject).first()
            subject.max_score = conf.max_score if conf else 100
        else:
            conf = ExamSubjectConfiguration.objects.filter(subject=subject).order_by('-exam_id').first()
            subject.max_score = conf.max_score if conf else 100
    
    for student_data in ranked_students:
        display_scores = []
        for subject in table_subjects:
            score_obj = student_data['subject_scores'].get(subject.name)
            display_scores.append(score_obj)
        student_data['display_scores'] = display_scores

    # Subject Averages
    subject_performance = []
    for subject in table_subjects:
        relevant_configs = [c for k, c in config_data_map.items() if k[1] == subject.id]
        ref_max = relevant_configs[0]['max_score'] if relevant_configs else 100
        
        subject_student_percentages = []
        for s_data in ranked_students:
            score_item = s_data['subject_scores'].get(subject.name)
            if score_item:
                student_s_max = config_data_map.get((score_item['exam_id'], subject.id), {}).get('max_score', ref_max)
                student_perc = (score_item['score'] / student_s_max) * 100 if student_s_max > 0 else 0
                subject_student_percentages.append(student_perc)
        
        s_avg_perc = sum(subject_student_percentages) / len(subject_student_percentages) if subject_student_percentages else 0
        subject_performance.append({
            'name': subject.name,
            'avg': round(s_avg_perc, 1),
            'grade': get_score_grade(s_avg_perc, class_obj.grade.name)
        })

    subject_footer_stats = {s['name']: s for s in subject_performance}
    total_avg = sum(s['avg_score'] for s in ranked_students)
    class_average = round(total_avg / len(ranked_students), 1) if ranked_students else 0

    context = {
        'class_obj': class_obj,
        'exam_obj': exam_obj,
        'ranked_students': ranked_students,
        'table_subjects': table_subjects,
        'class_average': class_average,
        'subject_footer_stats': subject_footer_stats,
        'selected_exam': selected_exam,
        'selected_subject': selected_subject,
        'is_junior_secondary': class_obj.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if class_obj.grade else False,
        'today': timezone.now(),
    }
    
    return render(request, 'core/class_merit_list.html', context)


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
            ).aggregate(avg=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))['avg'] or 0
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
        ).aggregate(avg=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))['avg'] or 0
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
    
    # Dynamically determine the grade list for charts and tallies
    is_junior_secondary = class_obj.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if class_obj.grade else False
    if is_junior_secondary:
        current_grade_list = ['EE1', 'EE2', 'ME1', 'ME2', 'AE1', 'AE2', 'BE1', 'BE2']
    else:
        current_grade_list = ['EE', 'ME', 'AE', 'BE']

    # Calculate Grade distribution
    grade_counts = current_scores.values('grade').annotate(total=Count('id'))
    grades_data = {g: 0 for g in current_grade_list}
    
    for item in grade_counts:
        g = item['grade']
        if g in grades_data:
            grades_data[g] = item['total']
            if g not in current_grade_list:
                current_grade_list.append(g)
        
    # Calculate aggregated counts for summary cards
    level_counts = {
        'EE': grades_data.get('EE', 0) + grades_data.get('EE1', 0) + grades_data.get('EE2', 0),
        'ME': grades_data.get('ME', 0) + grades_data.get('ME1', 0) + grades_data.get('ME2', 0),
        'AE': grades_data.get('AE', 0) + grades_data.get('AE1', 0) + grades_data.get('AE2', 0),
        'BE': grades_data.get('BE', 0) + grades_data.get('BE1', 0) + grades_data.get('BE2', 0),
    }
        
    # Calculate Gender distribution
    gender_stats = current_scores.values('student__gender').annotate(
        avg_score=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())),
        count=Count('id')
    )
    
    # Average Score
    avg_score = current_scores.aggregate(avg=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))['avg'] or 0
    
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
        ex_avg = ex_scores.aggregate(avg=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))['avg'] or 0
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
            ).aggregate(avg=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())))['avg'] or 0
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
        'is_junior_secondary': is_junior_secondary,
        'level_counts': level_counts,
        'previous_exam': previous_exam,
        'available_exams': subject_exams,
        # JSON for charts
        'historical_labels_js': json.dumps(historical_labels),
        'historical_averages_js': json.dumps(historical_averages),
        'comparative_datasets_js': json.dumps(get_comparative_trend_data(subject, class_obj, subject_exams)),
        # Grade Distribution Data
        'grade_labels_js': json.dumps(current_grade_list),
        'grade_data_js': json.dumps([grades_data.get(g, 0) for g in current_grade_list]),
        # Student Comparison Data (Current vs Prev)
        'chart_labels_js': json.dumps(chart_labels),
        'current_data_js': json.dumps(current_student_data),
        'prev_data_js': json.dumps(prev_student_data),
        'gender_labels_js': json.dumps(current_grade_list),
        'gender_male_data_js': json.dumps([current_scores.filter(grade=g, student__gender='male').count() for g in current_grade_list]),
        'gender_female_data_js': json.dumps([current_scores.filter(grade=g, student__gender='female').count() for g in current_grade_list]),
        'radar_labels_js': json.dumps(radar_labels),
        'radar_datasets_js': json.dumps(radar_datasets),
    }
    
    return render(request, 'core/subject_exam_analytics.html', context)


def generate_teacher_remarks(student, exam, current_avg, subject_data):
    """
    Generate short, accurate, human-like class teacher remarks
    based on current performance vs previous exam performance.
    """
    from Exam.models import ExamSUbjectScore
    
    # 1. Look for the previous exam specifically for this student
    prev_exam = Exam.objects.filter(
        year=exam.year, 
        created_at__lt=exam.created_at
    ).order_by('-created_at').first()

    prev_avg = None
    if prev_exam:
        # Calculate raw average for the previous exam
        prev_scores_raw = ExamSUbjectScore.objects.filter(
            student=student, 
            paper__exam_subject__exam=prev_exam
        ).select_related('paper__exam_subject__subject')
        
        if prev_scores_raw.exists():
            prev_subj_data = {}
            for s in prev_scores_raw:
                sid = s.paper.exam_subject.subject_id
                if sid not in prev_subj_data:
                    config = s.paper.exam_subject.exam.examsubjectconfiguration_set.filter(subject_id=sid).first()
                    prev_subj_data[sid] = {'score': 0, 'max': config.max_score if config else 100}
                prev_subj_data[sid]['score'] += s.score
            
            p_percs = [(d['score'] / d['max']) * 100 for d in prev_subj_data.values() if d['max'] > 0]
            if p_percs:
                prev_avg = sum(p_percs) / len(p_percs)

    # 2. Identify strongest and weakest current subjects
    valid_subjects = [d for d in subject_data.values() if d.get('max', 0) > 0]
    strong_subj = None
    weak_subj = None
    
    if valid_subjects:
        sorted_subs = sorted(valid_subjects, key=lambda x: (x['score'] / x['max']))
        weak_subj = sorted_subs[0]['name']
        strong_subj = sorted_subs[-1]['name']

    # 3. Build the remark
    if prev_avg:
        diff = current_avg - prev_avg
        assessment = "Improved significantly" if diff > 5 else ("Maintained steady" if diff > -2 else "Performance dropped")
        remark = f"{assessment} compared to last exam. "
    else:
        assessment = "Excellent" if current_avg >= 80 else ("Good" if current_avg >= 60 else ("Fair" if current_avg >= 40 else "Weak"))
        remark = f"{assessment} results this term. "

    if strong_subj:
        remark += f"Strong in {strong_subj}. "
    if weak_subj and (strong_subj != weak_subj or current_avg < 60):
        remark += f"Needs focus in {weak_subj}. "

    remark += "Consistent effort will lead to success."
    return remark


@login_required
def student_report(request, student_id, exam_id):
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

    # Calculate percentages, points and grades
    total_percentages = []
    is_junior_secondary = profile.class_id.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if profile and profile.class_id.grade else False
    
    for subj_id, data in subject_data.items():
        perc = (data['score'] / data['max']) * 100 if data['max'] > 0 else 0
        total_percentages.append(perc)
        
        # Determine score to display
        data['out_of'] = data['max']
        if is_junior_secondary:
            data['display_score'] = f"{round(perc)}%"
        else:
            data['display_score'] = data['score']

        # Determine grade for this aggregated subject score
        config = ExamSubjectConfiguration.objects.filter(exam=exam, subject_id=subj_id).first()
        if config:
            ranking = config.scoreranking_set.filter(min_score__lte=data['score'], max_score__gte=data['score']).first()
            if ranking:
                data['grade'] = ranking.grade
            else:
                # Fallback matching Junior Secondary 1/2 levels
                if is_junior_secondary:
                    if perc >= 90: data['grade'] = 'EE1'
                    elif perc >= 80: data['grade'] = 'EE2'
                    elif perc >= 70: data['grade'] = 'ME1'
                    elif perc >= 60: data['grade'] = 'ME2'
                    elif perc >= 50: data['grade'] = 'AE1'
                    elif perc >= 40: data['grade'] = 'AE2'
                    elif perc >= 20: data['grade'] = 'BE1'
                    else: data['grade'] = 'BE2'
                else:
                    if perc >= 80: data['grade'] = 'EE'
                    elif perc >= 60: data['grade'] = 'ME'
                    elif perc >= 40: data['grade'] = 'AE'
                    else: data['grade'] = 'BE'
        else:
            if is_junior_secondary:
                if perc >= 90: data['grade'] = 'EE1'
                elif perc >= 80: data['grade'] = 'EE2'
                elif perc >= 70: data['grade'] = 'ME1'
                elif perc >= 60: data['grade'] = 'ME2'
                elif perc >= 50: data['grade'] = 'AE1'
                elif perc >= 40: data['grade'] = 'AE2'
                elif perc >= 20: data['grade'] = 'BE1'
                else: data['grade'] = 'BE2'
            else:
                if perc >= 80: data['grade'] = 'EE'
                elif perc >= 60: data['grade'] = 'ME'
                elif perc >= 40: data['grade'] = 'AE'
                else: data['grade'] = 'BE'
        
        # Calculate Points (8-point scale for JSS, 4-point for others)
        point_map = {
            'EE1': 8, 'EE2': 7, 
            'ME1': 6, 'ME2': 5, 
            'AE1': 4, 'AE2': 3, 
            'BE1': 2, 'BE2': 1,
            'EE': 4, 'ME': 3, 'AE': 2, 'BE': 1
        }
        data['points'] = point_map.get(data['grade'], 1)

    student_average = round(sum(total_percentages) / len(total_percentages), 1) if total_percentages else 0
    
    # Summary Calculations
    total_marks = sum(d['score'] for d in subject_data.values())
    total_out_of = sum(d['max'] for d in subject_data.values())
    sum_points = sum(d['points'] for d in subject_data.values())
    num_subjects = len(subject_data)
    average_points = int(sum_points / num_subjects) if num_subjects > 0 else 0
    
    max_pts_per_subj = 8 if is_junior_secondary else 4
    total_max_points = num_subjects * max_pts_per_subj
    
    # Overall Performance Level based on points percentage
    pts_perc = (sum_points / total_max_points) * 100 if total_max_points > 0 else 0
    if is_junior_secondary:
        if pts_perc >= 87.5: overall_grade = 'EE1'
        elif pts_perc >= 75: overall_grade = 'EE2'
        elif pts_perc >= 62.5: overall_grade = 'ME1'
        elif pts_perc >= 50: overall_grade = 'ME2'
        elif pts_perc >= 37.5: overall_grade = 'AE1'
        elif pts_perc >= 25: overall_grade = 'AE2'
        elif pts_perc >= 12.5: overall_grade = 'BE1'
        else: overall_grade = 'BE2'
    else:
        if pts_perc >= 75: overall_grade = 'EE'
        elif pts_perc >= 50: overall_grade = 'ME'
        elif pts_perc >= 25: overall_grade = 'AE'
        else: overall_grade = 'BE'

    # Grade Category
    grade_name = profile.class_id.grade.name if profile and profile.class_id.grade else ""
    if grade_name in ['Play Group', 'PP1', 'PP2']:
        grade_category = "ECDE"
    elif grade_name in ['Grade 1', 'Grade 2', 'Grade 3']:
        grade_category = "Lower Primary"
    elif grade_name in ['Grade 4', 'Grade 5', 'Grade 6']:
        grade_category = "Upper Primary"
    elif grade_name in ['Grade 7', 'Grade 8', 'Grade 9']:
        grade_category = "Junior Secondary"
    else:
        grade_category = "ASSESSMENT"

    # Check for 3rd term opening date logic
    next_opening_date = exam.term.opening_date
    term_name = exam.term.name.lower()
    if '3' in term_name or 'third' in term_name:
        next_year = AcademicYear.objects.filter(start_date__gt=exam.year.start_date).order_by('start_date').first()
        if next_year:
            next_opening_date = next_year.start_date

    context = {
        'student': student,
        'exam': exam,
        'profile': profile,
        'class_obj': profile.class_id if profile else None,
        'subject_results': sorted(subject_data.values(), key=lambda x: x['name']),
        'student_average': student_average,
        'today': datetime.now().date(),
        'is_junior_secondary': is_junior_secondary,
        'grade_category': grade_category,
        'next_opening_date': next_opening_date,
        'next_opening_date': next_opening_date,
        'totals': {
            'marks': total_marks,
            'out_of': total_out_of,
            'points': average_points,
            'max_points': total_max_points,
            'grade': overall_grade
        },
        'teacher_remarks': generate_teacher_remarks(student, exam, student_average, subject_data)
    }
    return render(request, 'core/student_report.html', context)


@login_required
def bulk_class_reports(request, class_id, exam_id):
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

        # Calculate percentages, points and grades
        total_percentages = []
        is_junior_secondary = profile.class_id.grade.name in ['Grade 7', 'Grade 8', 'Grade 9'] if profile.class_id.grade else False
        
        for subj_id, data in subject_data.items():
            perc = (data['score'] / data['max']) * 100 if data['max'] > 0 else 0
            total_percentages.append(perc)
            
            # Determine score to display
            data['out_of'] = data['max']
            if is_junior_secondary:
                data['display_score'] = f"{round(perc)}%"
            else:
                data['display_score'] = data['score']

            config = data['config']
            if config:
                ranking = config.scoreranking_set.filter(min_score__lte=data['score'], max_score__gte=data['score']).first()
                if ranking:
                    data['grade'] = ranking.grade
                else:
                    if is_junior_secondary:
                        if perc >= 90: data['grade'] = 'EE1'
                        elif perc >= 80: data['grade'] = 'EE2'
                        elif perc >= 70: data['grade'] = 'ME1'
                        elif perc >= 60: data['grade'] = 'ME2'
                        elif perc >= 50: data['grade'] = 'AE1'
                        elif perc >= 40: data['grade'] = 'AE2'
                        elif perc >= 20: data['grade'] = 'BE1'
                        else: data['grade'] = 'BE2'
                    else:
                        if perc >= 80: data['grade'] = 'EE'
                        elif perc >= 60: data['grade'] = 'ME'
                        elif perc >= 40: data['grade'] = 'AE'
                        else: data['grade'] = 'BE'
            else:
                if is_junior_secondary:
                    if perc >= 90: data['grade'] = 'EE1'
                    elif perc >= 80: data['grade'] = 'EE2'
                    elif perc >= 70: data['grade'] = 'ME1'
                    elif perc >= 60: data['grade'] = 'ME2'
                    elif perc >= 50: data['grade'] = 'AE1'
                    elif perc >= 40: data['grade'] = 'AE2'
                    elif perc >= 20: data['grade'] = 'BE1'
                    else: data['grade'] = 'BE2'
                else:
                    if perc >= 80: data['grade'] = 'EE'
                    elif perc >= 60: data['grade'] = 'ME'
                    elif perc >= 40: data['grade'] = 'AE'
                    else: data['grade'] = 'BE'
            
            # Calculate Points (8-point scale for JSS, 4-point for others)
            point_map = {
                'EE1': 8, 'EE2': 7, 
                'ME1': 6, 'ME2': 5, 
                'AE1': 4, 'AE2': 3, 
                'BE1': 2, 'BE2': 1,
                'EE': 4, 'ME': 3, 'AE': 2, 'BE': 1
            }
            data['points'] = point_map.get(data['grade'], 1)

        student_average = round(sum(total_percentages) / len(total_percentages), 1) if total_percentages else 0
        
        # Summary Calculations
        total_marks = sum(d['score'] for d in subject_data.values())
        total_out_of = sum(d['max'] for d in subject_data.values())
        sum_points = sum(d['points'] for d in subject_data.values())
        num_subjects = len(subject_data)
        average_points = int(sum_points / num_subjects) if num_subjects > 0 else 0
        
        max_pts_per_subj = 8 if is_junior_secondary else 4
        total_max_points = num_subjects * max_pts_per_subj
        
        # Overall Performance Level based on points percentage
        pts_perc = (sum_points / total_max_points) * 100 if total_max_points > 0 else 0
        if is_junior_secondary:
            if pts_perc >= 87.5: overall_grade = 'EE1'
            elif pts_perc >= 75: overall_grade = 'EE2'
            elif pts_perc >= 62.5: overall_grade = 'ME1'
            elif pts_perc >= 50: overall_grade = 'ME2'
            elif pts_perc >= 37.5: overall_grade = 'AE1'
            elif pts_perc >= 25: overall_grade = 'AE2'
            elif pts_perc >= 12.5: overall_grade = 'BE1'
            else: overall_grade = 'BE2'
        else:
            if pts_perc >= 75: overall_grade = 'EE'
            elif pts_perc >= 50: overall_grade = 'ME'
            elif pts_perc >= 25: overall_grade = 'AE'
            else: overall_grade = 'BE'

        # Grade Category
        grade_name = profile.class_id.grade.name if profile and profile.class_id.grade else ""
        if grade_name in ['Play Group', 'PP1', 'PP2']:
            grade_category = "ECDE"
        elif grade_name in ['Grade 1', 'Grade 2', 'Grade 3']:
            grade_category = "Lower Primary"
        elif grade_name in ['Grade 4', 'Grade 5', 'Grade 6']:
            grade_category = "Upper Primary"
        elif grade_name in ['Grade 7', 'Grade 8', 'Grade 9']:
            grade_category = "Junior Secondary"
        else:
            grade_category = "ASSESSMENT"

        reports.append({
            'student': student,
            'profile': profile,
            'is_junior_secondary': is_junior_secondary,
            'grade_category': grade_category,
            'subject_results': sorted(subject_data.values(), key=lambda x: x['name']),
            'student_average': student_average,
            'totals': {
                'marks': total_marks,
                'out_of': total_out_of,
                'points': average_points,
                'max_points': total_max_points,
                'grade': overall_grade
            },
            'teacher_remarks': generate_teacher_remarks(student, exam, student_average, subject_data)
        })
    
    # Check for 3rd term opening date logic
    next_opening_date = exam.term.opening_date
    term_name = exam.term.name.lower()
    if '3' in term_name or 'third' in term_name:
        next_year = AcademicYear.objects.filter(start_date__gt=exam.year.start_date).order_by('start_date').first()
        if next_year:
            next_opening_date = next_year.start_date
    
    context = {
        'class_obj': class_obj,
        'exam': exam,
        'reports': reports,
        'today': today,
        'next_opening_date': next_opening_date,
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
    from django.db.models import Sum
    
    # Get all exams for the filter dropdown
    exams = Exam.objects.all().select_related('year', 'term').order_by('-id')
    
    selected_exam_id = request.GET.get('exam')
    selected_exam = None
    
    # Default to the latest exam if none selected
    if selected_exam_id and selected_exam_id.isdigit():
        selected_exam = Exam.objects.filter(id=selected_exam_id).select_related('year', 'term').first()
    
    if not selected_exam:
        selected_exam = exams.first()
    
    analytics_data = []  # list of grade-level data dicts

    if selected_exam:
        # Find all grades that have scores for this exam
        grade_names_with_scores = ExamSUbjectScore.objects.filter(
            paper__exam_subject__exam=selected_exam
        ).values_list(
            'paper__exam_subject__subject__grade', flat=True
        ).distinct()
        
        # Sort grades by the Grade.choices ordering
        grade_order = [c[0] for c in Grade.choices]
        sorted_grade_names = sorted(
            grade_names_with_scores,
            key=lambda g: grade_order.index(g) if g in grade_order else 999
        )
        
        for grade_name in sorted_grade_names:
            subjects = Subject.objects.filter(grade=grade_name).order_by('name')
            
            if not subjects.exists():
                continue
            
            classes = Class.objects.filter(grade__name=grade_name).select_related('school', 'grade')
            
            grade_data = {
                'grade_name': grade_name,
                'subjects': subjects,
                'streams': [],
                'top_students': [],  # top 3 across ALL streams/schools for this grade
            }
            
            for cls in classes:
                student_profiles = StudentProfile.objects.filter(class_id=cls, status='Active')
                student_ids = list(student_profiles.values_list('student_id', flat=True))
                
                if not student_ids:
                    continue
                
                stream = {
                    'class_obj': cls,
                    'class_name': cls.name,
                    'school_name': cls.school.name if cls.school else '',
                    'scores': [],
                    'total_mean': 0,
                    'student_count': len(student_ids),
                }
                
                has_any_score = False
                total_sum = 0
                
                for subject in subjects:
                    student_subject_totals = ExamSUbjectScore.objects.filter(
                        student_id__in=student_ids,
                        paper__exam_subject__exam=selected_exam,
                        paper__exam_subject__subject=subject
                    ).values('student_id').annotate(total_score=Sum('score'))
                    
                    if student_subject_totals:
                        mean_score = sum(item['total_score'] for item in student_subject_totals) / len(student_subject_totals)
                        has_any_score = True
                    else:
                        mean_score = 0
                        
                    stream['scores'].append(round(mean_score, 2))
                    total_sum += mean_score
                
                if not has_any_score:
                    continue
                
                stream['total_mean'] = round(total_sum, 2)
                grade_data['streams'].append(stream)
            
            if grade_data['streams']:
                # Tag highest scores per subject column
                for i in range(len(subjects)):
                    col_scores = [s['scores'][i] for s in grade_data['streams'] if s['scores'][i] > 0]
                    highest = max(col_scores) if col_scores else 0
                    for s in grade_data['streams']:
                        val = s['scores'][i]
                        s['scores'][i] = {
                            'value': val,
                            'is_highest': (val == highest and val > 0)
                        }
                
                # Sort streams by total mean descending
                grade_data['streams'].sort(key=lambda x: x['total_mean'], reverse=True)
                
                # ---- Top 3 students for this GRADE across ALL streams/schools ----
                all_student_ids = []
                for cls in classes:
                    ids = list(StudentProfile.objects.filter(
                        class_id=cls, status='Active'
                    ).values_list('student_id', flat=True))
                    all_student_ids.extend(ids)
                
                if all_student_ids:
                    student_totals = ExamSUbjectScore.objects.filter(
                        student_id__in=all_student_ids,
                        paper__exam_subject__exam=selected_exam,
                        paper__exam_subject__subject__grade=grade_name
                    ).values(
                        'student_id',
                        'student__first_name',
                        'student__last_name',
                        'student__adm_no',
                        'student__studentprofile__class_id__name',
                        'student__studentprofile__school__name',
                    ).annotate(
                        total=Sum('score')
                    ).order_by('-total')[:3]
                    
                    max_possible = ExamSubjectConfiguration.objects.filter(
                        exam=selected_exam,
                        subject__grade=grade_name
                    ).aggregate(total_max=Sum('max_score'))['total_max'] or 1
                    
                    for idx, st in enumerate(student_totals, 1):
                        avg_pct = round((st['total'] / max_possible) * 100, 1) if max_possible else 0
                        grade_data['top_students'].append({
                            'rank': idx,
                            'name': f"{st['student__first_name']} {st['student__last_name']}",
                            'adm_no': st['student__adm_no'],
                            'total': st['total'],
                            'avg': avg_pct,
                            'class_name': st['student__studentprofile__class_id__name'] or '',
                            'school_name': st['student__studentprofile__school__name'] or '',
                        })
                
                analytics_data.append(grade_data)
    
    context = {
        'exams': exams,
        'selected_exam': selected_exam,
        'selected_exam_id': str(selected_exam.id) if selected_exam else '',
        'analytics_data': analytics_data,
    }
    
    return render(request, 'core/schools_analytics.html', context)

@login_required
def discipline_log(request):
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role not in ['Admin', 'Teacher']:
        messages.error(request, 'You do not have permission to view discipline logs.')
        return redirect('core:dashboard')

    if request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'Admin'):
        incidents = StudentDiscipline.objects.select_related('student', 'student__studentprofile__class_id', 'reported_by').order_by('-date')
    else:
        incidents = StudentDiscipline.objects.select_related('student', 'student__studentprofile__class_id', 'reported_by').filter(reported_by=request.user).order_by('-date')
        
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
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role not in ['Admin', 'Teacher']:
        messages.error(request, 'You do not have permission to delete discipline logs.')
        return redirect('core:dashboard')

    incident = get_object_or_404(StudentDiscipline, id=incident_id)
    
    if not request.user.is_superuser and hasattr(request.user, 'role') and request.user.role != 'Admin':
        if incident.reported_by != request.user:
            messages.error(request, "You can only delete incidents that you reported.")
            return redirect('core:discipline-log')
            
    student_name = incident.student.first_name
    incident.delete()
    messages.success(request, f"Discipline record for {student_name} deleted.")
    return redirect('core:discipline-log')


class ReportDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/reports.html'

    def test_func(self):
        return self.request.user.role == 'Admin' or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import datetime
        report_type = self.request.GET.get('type', 'students')
        school_id = self.request.GET.get('school')
        grade_id = self.request.GET.get('grade')
        class_id = self.request.GET.get('class')
        date_from_str = self.request.GET.get('date_from')
        date_to_str = self.request.GET.get('date_to')
        exam_id = self.request.GET.get('exam')
        
        context['report_type'] = report_type
        context['selected_exam'] = exam_id
        context['exams'] = Exam.objects.all().order_by('-id')
        context['selected_school'] = school_id
        context['selected_grade'] = grade_id
        context['selected_class'] = class_id
        context['selected_date_from'] = date_from_str
        context['selected_date_to'] = date_to_str
        context['schools'] = School.objects.all().order_by('name')
        
        grades_qs = Grade.objects.all().order_by('name')
        if school_id:
            grades_qs = grades_qs.filter(school_id=school_id)
        context['grades'] = grades_qs
        if grade_id:
            context['selected_grade_obj'] = grades_qs.filter(id=grade_id).first()
        context['selected_school'] = school_id
        context['selected_grade'] = grade_id
        context['selected_class'] = class_id
        context['selected_date_from'] = date_from_str
        context['selected_date_to'] = date_to_str

        date_from = None
        date_to = None
        try:
            if date_from_str:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            if date_to_str:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass

        # Build classes queryset with cascading filters
        classes_qs = Class.objects.all().select_related('grade')
        if school_id:
            classes_qs = classes_qs.filter(school_id=school_id)
        if grade_id:
            classes_qs = classes_qs.filter(grade_id=grade_id)
        context['classes'] = classes_qs

        if report_type == 'students':
            queryset = StudentProfile.objects.all().select_related('student', 'class_id', 'school')
            if school_id:
                queryset = queryset.filter(school_id=school_id)
            if grade_id:
                queryset = queryset.filter(class_id__grade_id=grade_id)
            if class_id:
                queryset = queryset.filter(class_id_id=class_id)
            if date_from:
                queryset = queryset.filter(student__joined_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(student__joined_date__lte=date_to)
            
            # Stat Cards Data
            context['total_students'] = queryset.count()
            context['active_students'] = queryset.filter(status='Active').count()
            context['graduated_students'] = queryset.filter(status='Graduated').count()
            context['inactive_students'] = queryset.filter(status='Inactive').count()

            # Distribution by School (for Chart)
            context['school_distribution'] = list(queryset.values('school__name').annotate(count=Count('id')).order_by('-count'))
            
            # Distribution by Grade (for Chart)
            context['grade_distribution'] = list(queryset.values('class_id__grade__name').annotate(count=Count('id')).order_by('-count'))
            
            context['report_data'] = queryset.order_by('?')[:100]
            
        elif report_type == 'fees':
            balance_status = self.request.GET.get('balance_status')
            
            # Start with all students to calculate balances, then filter for payments later
            all_profiles = StudentProfile.objects.all().select_related('student', 'school', 'class_id')
            if school_id:
                all_profiles = all_profiles.filter(school_id=school_id)
            if grade_id:
                all_profiles = all_profiles.filter(class_id__grade_id=grade_id)
            if class_id:
                all_profiles = all_profiles.filter(class_id_id=class_id)
            
            # Filter payment queryset
            queryset = Payment.objects.all().select_related('student', 'student__studentprofile__school', 'student__studentprofile__class_id')
            if school_id:
                queryset = queryset.filter(student__studentprofile__school_id=school_id)
            if grade_id:
                queryset = queryset.filter(student__studentprofile__class_id__grade_id=grade_id)
            if class_id:
                queryset = queryset.filter(student__studentprofile__class_id_id=class_id)
            if date_from:
                queryset = queryset.filter(date_paid__gte=date_from)
            if date_to:
                queryset = queryset.filter(date_paid__lte=date_to)
            
            # Apply balance status filter to profiles if requested
            if balance_status == 'owing':
                all_profiles = all_profiles.filter(fee_balance__gt=0)
            elif balance_status == 'overpaid':
                all_profiles = all_profiles.filter(fee_balance__lt=0)
            elif balance_status == 'cleared':
                all_profiles = all_profiles.filter(fee_balance=0)
            
            # If filtering by balance status, we want to show payments from those students
            if balance_status:
                student_ids = all_profiles.values_list('student_id', flat=True)
                queryset = queryset.filter(student_id__in=student_ids)
                context['selected_balance_status'] = balance_status
            
            # Stat Cards Data
            context['total_collected'] = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
            context['transaction_count'] = queryset.count()
            context['avg_payment'] = context['total_collected'] / context['transaction_count'] if context['transaction_count'] > 0 else 0
            
            # Collection Trend (Last 6 Months)
            six_months_ago = timezone.now() - timedelta(days=180)
            context['collection_trend'] = list(queryset.filter(date_paid__gte=six_months_ago)
                                            .annotate(month=TruncMonth('date_paid'))
                                            .values('month')
                                            .annotate(total=Sum('amount'))
                                            .order_by('month'))

            # Collection by School
            context['fee_school_distribution'] = list(queryset.values('student__studentprofile__school__name')
                                                   .annotate(total=Sum('amount'))
                                                   .order_by('-total'))

            # Balance & Overpayment Analytics (calculated from the scoped all_profiles)
            balances = all_profiles.aggregate(
                total_debt=Sum(Case(When(fee_balance__gt=0, then=F('fee_balance')), default=0)),
                total_overpaid=Sum(Case(When(fee_balance__lt=0, then=F('fee_balance')), default=0))
            )
            context['total_debt'] = balances['total_debt'] or 0
            context['total_overpaid'] = abs(balances['total_overpaid'] or 0)
            
            context['owing_count'] = all_profiles.filter(fee_balance__gt=0).count()
            
            context['report_data'] = queryset.order_by('-date_paid')
            
        elif report_type == 'performance':
            # Basic performance overview
            queryset = ExamSUbjectScore.objects.all().select_related('student', 'paper__exam_subject__exam', 'class_id')
            if school_id:
                queryset = queryset.filter(student__studentprofile__school_id=school_id)
            if grade_id:
                queryset = queryset.filter(class_id__grade_id=grade_id)
            if class_id:
                queryset = queryset.filter(class_id_id=class_id)
            if exam_id:
                queryset = queryset.filter(paper__exam_subject__exam_id=exam_id)
            if date_from:
                queryset = queryset.filter(paper__exam_subject__exam__created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(paper__exam_subject__exam__created_at__date__lte=date_to)
            
            # Group by exam for a high level view
            context['report_data'] = queryset.values(
                'paper__exam_subject__exam__name', 
                'paper__exam_subject__exam__year__start_date__year'
            ).annotate(
                avg_score=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField())),
                total_entries=Count('id')
            ).order_by('-paper__exam_subject__exam__created_at')

            # NEW: Distribution data for charts
            # 1. Grade-level counts
            context['performance_grade_dist'] = list(queryset.values('grade').annotate(count=Count('id')).order_by('grade'))
            
            # 2. Subject-wise performance
            context['performance_subject_dist'] = list(queryset.values('paper__exam_subject__subject__name').annotate(
                avg_score=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField()))
            ).order_by('-avg_score'))[:12] # Limit to top 12 subjects for clarity

            # 3. Stream comparison (if grade is selected but No stream is chosen)
            if grade_id and not class_id:
                context['stream_comparison'] = list(queryset.values('class_id__name').annotate(
                    avg_score=Avg(ExpressionWrapper(F('score') * 100.0 / F('paper__out_of'), output_field=FloatField()))
                ).order_by('class_id__name'))

        return context


class AttendanceAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "core/attendance_analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Handle Filtering
        date_str = self.request.GET.get("date")
        date_from_str = self.request.GET.get("date_from")
        date_to_str = self.request.GET.get("date_to")
        
        today = timezone.now().date()
        target_date = today
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        
        date_from = target_date
        date_to = target_date
        
        if date_from_str and date_to_str:
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        
        context["target_date"] = target_date
        context["date_from"] = date_from
        context["date_to"] = date_to
        
        # 2. Scope by school if needed
        school = None
        if not self.request.user.is_superuser:
            try:
                school = self.request.user.profile.school
            except AttributeError:
                pass
        
        # 3. Analytics for the selected range
        sessions = AttendanceSession.objects.filter(date__gte=date_from, date__lte=date_to)
        if school:
            sessions = sessions.filter(class_id__grade__school=school)
            
        stats = StudentAttendance.objects.filter(session__in=sessions).aggregate(
            present=Count("id", filter=Q(status="Present")),
            absent=Count("id", filter=Q(status="Absent")),
            late=Count("id", filter=Q(status="Late")),
            half_day=Count("id", filter=Q(status="Half Day"))
        )
        context["stats"] = stats
        context["total_records"] = sum(v for v in stats.values() if v)
        
        # Calculate percentages
        if context["total_records"] > 0:
            context["present_perc"] = round((stats["present"] / context["total_records"]) * 100, 1)
            context["absent_perc"] = round((stats["absent"] / context["total_records"]) * 100, 1)
            context["late_perc"] = round(((stats["late"] + stats["half_day"]) / context["total_records"]) * 100, 1)
        else:
            context["present_perc"] = context["absent_perc"] = context["late_perc"] = 0

        # 4. Table of non-present students
        non_present_records = (
            StudentAttendance.objects.filter(
                session__in=sessions,
                status__in=["Absent", "Late", "Half Day"]
            )
            .select_related("student", "session__class_id")
            .order_by("-session__date", "student__first_name")
        )
        context["non_present_students"] = non_present_records
        
        # 5. Classes with missing attendance for target_date
        all_classes = Class.objects.all().select_related("grade__school")
        if school:
            all_classes = all_classes.filter(grade__school=school)
            
        marked_classes_ids = sessions.filter(date=target_date).values_list("class_id_id", flat=True)
        missing_attendance_classes = all_classes.exclude(id__in=marked_classes_ids)
        context["missing_classes"] = missing_attendance_classes
        
        return context


@login_required
def link_student_view(request):
    """View to link students to users (guardians)"""
    from users.models import MyUser
    
    # Check permissions - admin and superuser can link students
    if not request.user.is_superuser and request.user.role != 'Admin':
        messages.error(request, 'You do not have permission to link students.')
        return redirect('core:dashboard')
    
    # Get all users who can be guardians
    users = MyUser.objects.filter(
        role__in=['Admin', 'Teacher', 'Accountant', 'Receptionist', 'Guardian']
    ).prefetch_related('students')
    
    # Get all students
    students = Student.objects.all().select_related('studentprofile__school')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        student_ids = request.POST.getlist('student_ids')
        
        if not user_id:
            messages.error(request, "Please select a user first.")
            return redirect('core:link-student')
        
        try:
            user = MyUser.objects.get(id=user_id)
            
            # Clear existing student links for this user
            user.students.clear()
            
            # Add new student links
            if student_ids:
                students_to_link = Student.objects.filter(id__in=student_ids)
                user.students.add(*students_to_link)
                
                messages.success(request, f"Successfully linked {len(students_to_link)} students to {user.get_full_name() or user.email}")
            else:
                messages.info(request, f"Cleared all student links for {user.get_full_name() or user.email}")
                
        except MyUser.DoesNotExist:
            messages.error(request, "User not found")
        except Exception as e:
            messages.error(request, f"Error linking students: {str(e)}")
            
    # Prepare current links mapping for JS
    user_links = {user.id: list(user.students.values_list('id', flat=True)) for user in users}
    
    # Get unique schools and grades for filters
    from .models import School, Grade
    schools = School.objects.all().order_by('name')
    grades = Grade.objects.all().order_by('name')
    
    context = {
        'users': users,
        'students': students,
        'schools': schools,
        'grades': grades,
        'user_links_json': json.dumps(user_links),
        'title': 'Link Students to Users'
    }
    
    return render(request, 'core/link_student.html', context)

@login_required
def migrate_year(request):
    """
    Promotes students to the next grade and activates the selected academic year.
    Exceptions (PP2 -> Grade 1, Grade 6 -> Grade 7) are cleared from classes 
    for manual reshuffling. Supports AJAX chunked processing.
    """
    if not request.user.is_superuser and getattr(request.user, 'role', '') != 'Admin':
        messages.error(request, "Permission denied.")
        return redirect('core:configurations')

    if request.method == 'POST':
        action = request.POST.get('action')
        year_id = request.POST.get('target_year') or request.POST.get('year_id')
        
        if not year_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Target year not specified.'})
            messages.error(request, "Target year not specified.")
            return redirect('core:migrate-year')

        try:
            target_year = AcademicYear.objects.get(id=year_id)
        except AcademicYear.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Target year does not exist.'})
            messages.error(request, "Target year does not exist.")
            return redirect('core:migrate-year')

        if action == 'prepare':
            # 1. Activate Year & Term
            AcademicYear.objects.all().update(is_active=False)
            target_year.is_active = True
            target_year.save()

            Term.objects.all().update(is_active=False)
            target_term = Term.objects.filter(name__icontains='1').first()
            if not target_term:
                target_term = Term.objects.first()
            
            if target_term:
                target_term.is_active = True
                target_term.save()

            # 2. Get Student IDs for chunks
            skip_classes = request.POST.getlist('skip_classes[]')
            students_qs = StudentProfile.objects.filter(status='Active')
            
            if skip_classes:
                students_qs = students_qs.exclude(class_id_id__in=skip_classes)
            
            student_ids = list(students_qs.values_list('id', flat=True))
            
            return JsonResponse({
                'status': 'ok',
                'total': len(student_ids),
                'student_ids': student_ids,
                'year_name': str(target_year)
            })

        elif action == 'migrate_chunk':
            student_ids = request.POST.getlist('student_ids[]')
            if not student_ids:
                return JsonResponse({'status': 'error', 'message': 'No students specified.'})

            target_term = Term.objects.filter(is_active=True).first()
            
            # Pre-fetch fee structures for the active term to avoid N+1 queries
            # Key: (school_id, grade_id, student_type) -> FeeStructure object
            fee_map = {}
            if target_term:
                f_structures = FeeStructure.objects.filter(term=target_term).prefetch_related('grade')
                for fs in f_structures:
                    for grade in fs.grade.all():
                        fee_map[(fs.school_id, grade.id, fs.student_type)] = fs

            grade_sequence = [
                'Play Group', 'PP1', 'PP2', 'Grade 1', 'Grade 2', 'Grade 3', 
                'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9'
            ]
            
            profiles = StudentProfile.objects.filter(id__in=student_ids).select_related('class_id', 'class_id__grade', 'school', 'student')
            stats = {'success': 0, 'manual': 0, 'skipped': 0, 'invoices': 0}
            
            skip_classes = request.POST.getlist('skip_classes[]')
            
            from django.db import transaction
            with transaction.atomic():
                for profile in profiles:
                    # 1. Guard against duplicate promotion in the same year
                    if PromotionHistory.objects.filter(student=profile.student, academic_year=target_year).exists():
                        stats['skipped'] += 1
                        continue

                    current_cl = profile.class_id
                    if not current_cl:
                        stats['skipped'] += 1
                        continue
                    
                    curr_gr_name = current_cl.grade.name
                    
                    if curr_gr_name == 'PP2' or curr_gr_name == 'Grade 6':
                        old_cl = profile.class_id
                        profile.class_id = None
                        profile.save()
                        PromotionHistory.objects.create(
                            student=profile.student, from_class=old_cl, to_class=None, academic_year=target_year
                        )
                        stats['manual'] += 1
                        continue
                    
                    try:
                        curr_idx = grade_sequence.index(curr_gr_name)
                        if curr_idx < len(grade_sequence) - 1:
                            next_gr_name = grade_sequence[curr_idx + 1]
                            next_cl = Class.objects.filter(
                                grade__name=next_gr_name, name=current_cl.name, school=profile.school
                            ).first()
                            
                            if next_cl:
                                old_cl = profile.class_id
                                profile.class_id = next_cl
                                profile.save()
                                PromotionHistory.objects.create(
                                    student=profile.student, from_class=old_cl, to_class=next_cl, academic_year=target_year
                                )
                                stats['success'] += 1
                                
                                # Billing Logic
                                if target_term:
                                    fee_type = profile.student.get_fee_student_type()
                                    fs = fee_map.get((profile.school_id, next_cl.grade_id, fee_type))
                                    
                                    if fs:
                                        # 2. Guard against duplicate invoicing for the same fee structure and calendar year
                                        target_cal_year = target_year.start_date.year
                                        if not Invoice.objects.filter(student=profile.student, fee_structure=fs, created_at__year=target_cal_year).exists():
                                            multiplier = profile.student.get_fee_multiplier()
                                            final_amount = fs.amount * Decimal(str(multiplier))
                                            
                                            Invoice.objects.create(
                                                student=profile.student,
                                                fee_structure=fs,
                                                amount=final_amount,
                                                description=f"First Term Fees - Academic Year {target_year}"
                                            )
                                            stats['invoices'] += 1

                                        # 3. Invoice Additional Charges
                                        from accounts.models import AdditionalCharges
                                        add_charges = AdditionalCharges.objects.filter(school=profile.school, grades=next_cl.grade)
                                        for ac in add_charges:
                                            # Guard against duplicate invoicing for additional charges
                                            if ac.amount and not Invoice.objects.filter(student=profile.student, description__icontains=ac.name, created_at__year=target_cal_year).exists():
                                                Invoice.objects.create(
                                                    student=profile.student,
                                                    amount=ac.amount,
                                                    description=f"{ac.name} for {next_cl.grade.name} - Academic Year {target_year}"
                                                )
                                                stats['invoices'] += 1
                            else:
                                old_cl = profile.class_id
                                profile.class_id = None
                                profile.save()
                                PromotionHistory.objects.create(
                                    student=profile.student, from_class=old_cl, to_class=None, academic_year=target_year
                                )
                                stats['skipped'] += 1
                        else:
                            # Graduation for last grade
                            old_cl = profile.class_id
                            profile.class_id = None
                            profile.status = 'Graduated'
                            profile.save()
                            PromotionHistory.objects.create(
                                student=profile.student, from_class=old_cl, to_class=None, academic_year=target_year, is_graduation=True
                            )
                            stats['success'] += 1
                    except ValueError:
                        stats['skipped'] += 1
            
            return JsonResponse({'status': 'ok', 'stats': stats})

    current_year = AcademicYear.objects.filter(is_active=True).first()
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    classes = Class.objects.select_related('grade', 'school').all().order_by('grade__name', 'name')
    
    return render(request, 'core/migrate_year.html', {
        'current_year': current_year,
        'academic_years': academic_years,
        'classes': classes
    })
