from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import Payment, FeeStructure, Invoice, StaffSalary, StaffPayment
from core.models import School, Student, StudentProfile
from users.models import MyUser
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
import json
from datetime import datetime, timedelta
from decimal import Decimal

class FeesAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/fees_analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filters
        school_id = self.request.GET.get('school')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        balance_type = self.request.GET.get('balance') # positive, negative, zero

        # Base Querysets
        payments = Payment.objects.all()
        profiles = StudentProfile.objects.all()

        if school_id:
            payments = payments.filter(student__studentprofile__school_id=school_id)
            profiles = profiles.filter(school_id=school_id)
        
        if date_from:
            payments = payments.filter(date_paid__gte=date_from)
        if date_to:
            payments = payments.filter(date_paid__lte=date_to)

        if balance_type == 'positive':
            profiles = profiles.filter(fee_balance__gt=0)
        elif balance_type == 'negative':
            profiles = profiles.filter(fee_balance__lt=0)
        elif balance_type == 'zero':
            profiles = profiles.filter(fee_balance=0)

        # Dashboard Stats
        context['total_collected'] = payments.aggregate(Sum('amount'))['amount__sum'] or 0
        context['total_invoiced'] = Invoice.objects.filter(student__studentprofile__in=profiles).aggregate(Sum('amount'))['amount__sum'] or 0
        context['pending_balance'] = profiles.aggregate(Sum('fee_balance'))['fee_balance__sum'] or 0
        context['student_count'] = profiles.count()

        # 1. Donut Chart: Payments per School (Filtered by Date)
        school_distribution = []
        grand_total = context['total_collected']
        
        # We want to see all schools, but their totals must respect the date filters
        for school in School.objects.all():
            amt = Payment.objects.filter(student__studentprofile__school=school)
            if date_from: amt = amt.filter(date_paid__gte=date_from)
            if date_to: amt = amt.filter(date_paid__lte=date_to)
            # If a school filter is active, only that school should have its full total
            if school_id and str(school.id) != school_id:
                total = 0
            else:
                total = amt.aggregate(Sum('amount'))['amount__sum'] or 0
            
            percentage = (float(total) / float(grand_total) * 100) if grand_total > 0 else 0
            
            school_distribution.append({
                'name': school.name,
                'total': float(total),
                'percentage': round(percentage, 1)
            })
        
        # Sort by total descending
        school_distribution.sort(key=lambda x: x['total'], reverse=True)
        context['school_distribution'] = school_distribution
        context['school_distribution_json'] = json.dumps(school_distribution)

        # 2. Line Chart: Monthly Collections (Last 6 Months)
        monthly_trends = []
        today = timezone.now().date()
        for i in range(5, -1, -1):
            month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            amt = Payment.objects.filter(date_paid__range=[month_start, month_end])
            if school_id: amt = amt.filter(student__studentprofile__school_id=school_id)
            
            total = amt.aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_trends.append({
                'month': month_start.strftime('%b %Y'),
                'total': float(total)
            })
        context['monthly_trends_json'] = json.dumps(monthly_trends)

        # 3. Balance Distribution Stats (Filtered)
        pos_count = profiles.filter(fee_balance__gt=0).count()
        neg_count = profiles.filter(fee_balance__lt=0).count()
        zero_count = profiles.filter(fee_balance=0).count()
        total_students = profiles.count()
        
        context['pos_bal_count'] = pos_count
        context['pos_bal_sum'] = profiles.filter(fee_balance__gt=0).aggregate(Sum('fee_balance'))['fee_balance__sum'] or 0
        context['pos_bal_pct'] = (pos_count / total_students * 100) if total_students > 0 else 0
        
        context['neg_bal_count'] = neg_count
        context['neg_bal_sum'] = profiles.filter(fee_balance__lt=0).aggregate(Sum('fee_balance'))['fee_balance__sum'] or 0
        context['neg_bal_pct'] = (neg_count / total_students * 100) if total_students > 0 else 0
        
        context['zero_bal_count'] = zero_count
        context['zero_bal_pct'] = (zero_count / total_students * 100) if total_students > 0 else 0

        # Metadata for Filters
        context['schools'] = School.objects.all()
        context['selected_school'] = school_id
        context['date_from'] = date_from
        context['date_to'] = date_to
        context['selected_balance'] = balance_type
        
        return context

from django.views.generic import ListView

class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'accounts/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 25

    def get_queryset(self):
        queryset = Payment.objects.all().select_related('student', 'student__studentprofile', 'recorded_by').order_by('-date_paid', '-created_at')
        
        # Filters
        query = self.request.GET.get('q')
        school_id = self.request.GET.get('school')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        method = self.request.GET.get('method')

        if query:
            queryset = queryset.filter(
                Q(student__first_name__icontains=query) | 
                Q(student__last_name__icontains=query) | 
                Q(student__adm_no__icontains=query)
            )
        
        if school_id:
            queryset = queryset.filter(student__studentprofile__school_id=school_id)
            
        if date_from:
            queryset = queryset.filter(date_paid__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_paid__lte=date_to)
            
        if method:
            queryset = queryset.filter(method=method)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Summary Stats
        context['total_filtered_amount'] = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Filter Metadata
        context['schools'] = School.objects.all()
        context['payment_methods'] = Payment.PAYMENT_METHODS
        
        # Current Filters
        context['q'] = self.request.GET.get('q', '')
        context['selected_school'] = self.request.GET.get('school', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['selected_method'] = self.request.GET.get('method', '')
        
        return context

class PayrollListView(LoginRequiredMixin, ListView):
    model = MyUser
    template_name = 'accounts/payroll_list.html'
    context_object_name = 'staff_members'
    paginate_by = 25

    def get_queryset(self):
        # Filter only staff-related roles
        queryset = MyUser.objects.filter(role__in=['Admin', 'Teacher', 'Accountant', 'Receptionist']).order_by('role', 'first_name')
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query) | 
                Q(email__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure every staff in queryset has a StaffSalary profile
        for staff in context['staff_members']:
            StaffSalary.objects.get_or_create(staff=staff)

        # Date filters
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        context['date_from'] = date_from
        context['date_to'] = date_to
        context['q'] = self.request.GET.get('q', '')
        context['q_voucher'] = self.request.GET.get('q_voucher', '')

        # Filtered staff payments base queryset
        staff_payments_qs = StaffPayment.objects.all()
        if date_from:
            staff_payments_qs = staff_payments_qs.filter(payment_date__gte=date_from)
        if date_to:
            staff_payments_qs = staff_payments_qs.filter(payment_date__lte=date_to)

        # Stat cards
        context['total_staff'] = self.get_queryset().count()
        context['total_unpaid'] = StaffSalary.objects.aggregate(Sum('salary_balance'))['salary_balance__sum'] or 0
        context['total_paid'] = staff_payments_qs.aggregate(Sum('amount'))['amount__sum'] or 0

        # Donut Chart
        roles_dist = list(self.get_queryset().values('role').annotate(count=Count('id')))
        context['roles_distribution_json'] = json.dumps(roles_dist)
        context['total_roles'] = len(roles_dist)

        # Bar Chart – monthly payroll (respects date filter window)
        today = timezone.now().date()
        monthly_summary = []
        for i in range(5, -1, -1):
            ms = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            me = (ms + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            bar_qs = StaffPayment.objects.filter(payment_date__range=[ms, me])
            if date_from:
                bar_qs = bar_qs.filter(payment_date__gte=date_from)
            if date_to:
                bar_qs = bar_qs.filter(payment_date__lte=date_to)
            amt = bar_qs.aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_summary.append({'month': ms.strftime('%b %Y'), 'total': float(amt)})
        context['monthly_summary_json'] = json.dumps(monthly_summary)

        # Line Chart – income (fee payments)
        fee_payments_qs = Payment.objects.all()
        if date_from:
            fee_payments_qs = fee_payments_qs.filter(date_paid__gte=date_from)
        if date_to:
            fee_payments_qs = fee_payments_qs.filter(date_paid__lte=date_to)

        monthly_income = []
        for i in range(5, -1, -1):
            ms = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            me = (ms + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            line_qs = Payment.objects.filter(date_paid__range=[ms, me])
            if date_from:
                line_qs = line_qs.filter(date_paid__gte=date_from)
            if date_to:
                line_qs = line_qs.filter(date_paid__lte=date_to)
            amt = line_qs.aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_income.append({'month': ms.strftime('%b %Y'), 'total': float(amt)})
        context['monthly_income_json'] = json.dumps(monthly_income)
        context['total_income'] = sum(m['total'] for m in monthly_income)

        # Payment vouchers table (filtered + searchable)
        vouchers_qs = staff_payments_qs.select_related('staff').order_by('-payment_date', '-created_at')
        q_voucher = self.request.GET.get('q_voucher', '')
        if q_voucher:
            vouchers_qs = vouchers_qs.filter(
                Q(staff__first_name__icontains=q_voucher) |
                Q(staff__last_name__icontains=q_voucher) |
                Q(reference__icontains=q_voucher)
            )
        context['recent_payments'] = vouchers_qs[:10]

        return context

@login_required
def process_payroll_payment(request, staff_id):
    staff = get_object_or_404(MyUser, id=staff_id)
    salary_profile, created = StaffSalary.objects.get_or_create(staff=staff)
    
    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        if amount_str:
            amount = Decimal(amount_str)
        else:
            amount = Decimal('0')
            
        method = request.POST.get('method')
        reference = request.POST.get('reference')
        payment_date = request.POST.get('payment_date') or timezone.now().date()
        
        if amount <= 0:
            messages.error(request, "Payment amount must be greater than zero.")
        else:
            try:
                StaffPayment.objects.create(
                    staff=staff,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=method,
                    reference=reference,
                    recorded_by=request.user
                )
                messages.success(request, f"Successfully processed payment of {amount} for {staff.get_full_name()}.")
                return redirect('accounts:payroll-list')
            except Exception as e:
                messages.error(request, f"Error processing payment: {str(e)}")
            
    return render(request, 'accounts/process_payroll.html', {
        'staff': staff,
        'salary_profile': salary_profile,
        'payment_methods': [('Cash', 'Cash'), ('Bank', 'Bank Transfer'), ('Mpesa', 'Mpesa')]
    })

@login_required
def update_salary_config(request, staff_id):
    staff = get_object_or_404(MyUser, id=staff_id)
    salary_profile, created = StaffSalary.objects.get_or_create(staff=staff)
    
    if request.method == 'POST':
        basic_salary_str = request.POST.get('basic_salary', '0')
        if basic_salary_str:
            basic_salary = Decimal(basic_salary_str)
            salary_profile.basic_salary = basic_salary
        
        adjustment_str = request.POST.get('balance_adjustment', '0')
        if adjustment_str:
            adjustment = Decimal(adjustment_str)
            salary_profile.salary_balance += adjustment
        
        salary_profile.save()
        messages.success(request, f"Updated salary configuration for {staff.get_full_name()}.")
        
    return redirect('accounts:payroll-list')

class MigrateFeesView(LoginRequiredMixin, ListView):
    template_name = 'accounts/migrate_fees.html'
    context_object_name = 'student_profiles'

    def get_queryset(self):
        from core.models import Grade
        grade_id = self.request.GET.get('grade')
        
        # Default to first grade if none selected
        if grade_id:
            queryset = StudentProfile.objects.filter(class_id__grade_id=grade_id)
        else:
            first_grade = Grade.objects.all().first()
            if first_grade:
                queryset = StudentProfile.objects.filter(class_id__grade=first_grade)
            else:
                queryset = StudentProfile.objects.none()

        queryset = queryset.select_related('student', 'class_id', 'class_id__grade', 'school')
        
        # Filter by school if user is linked to one
        if self.request.user.school:
            queryset = queryset.filter(school=self.request.user.school)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import Term, AcademicYear, Grade
        
        active_term = Term.objects.filter(is_active=True).first()
        active_year = AcademicYear.objects.filter(is_active=True).first()
        
        selected_grade_id = self.request.GET.get('grade')
        if selected_grade_id:
            selected_grade = Grade.objects.filter(id=selected_grade_id).first()
        else:
            selected_grade = Grade.objects.all().first()

        context['active_term'] = active_term
        context['active_year'] = active_year
        context['grades'] = Grade.objects.all()
        context['selected_grade'] = selected_grade
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.user.role != 'Admin' and request.user.role != 'Accountant':
            messages.error(request, "Permission denied.")
            return redirect('accounts:migrate-fees')

        action = request.POST.get('action')
        
        from core.models import Term, AcademicYear
        active_term = Term.objects.filter(is_active=True).first()
        active_year = AcademicYear.objects.filter(is_active=True).first()
        
        if not active_term or not active_year:
            messages.error(request, "No active term/year set.")
            return redirect('accounts:migrate-fees')
            
        def get_structure_for_student(profile):
            # Map student status to student_type
            s_type = 'boarder' if profile.student.is_boarder else 'day'
            # Find structure for this student's school, type, grade, year, and term
            return FeeStructure.objects.filter(
                academic_year=active_year,
                term=active_term,
                school=profile.school,
                student_type=s_type,
                grade=profile.class_id.grade
            ).first()

        if action == 'invoice_all':
            profiles = self.get_queryset()
            invoice_count = 0
            missing_structure_count = 0
            
            for profile in profiles:
                fee_structure = get_structure_for_student(profile)
                if not fee_structure:
                    missing_structure_count += 1
                    continue
                    
                if not Invoice.objects.filter(student=profile.student, fee_structure=fee_structure).exists():
                    Invoice.objects.create(
                        student=profile.student,
                        fee_structure=fee_structure,
                        amount=fee_structure.amount
                    )
                    invoice_count += 1
            
            msg = f"Successfully created {invoice_count} invoices."
            if missing_structure_count > 0:
                msg += f" {missing_structure_count} students skipped due to missing fee structures."
            messages.success(request, msg)

        elif action == 'invoice_single':
            student_id = request.POST.get('student_id')
            student = get_object_or_404(Student, id=student_id)
            profile = student.studentprofile
            fee_structure = get_structure_for_student(profile)
            
            if not fee_structure:
                messages.error(request, f"No fee structure found for {student.get_full_name()} (School: {student.profile.school.name}, Type: {'Boarder' if student.is_boarder else 'Day Scholar'}).")
                return redirect('accounts:migrate-fees')

            if not Invoice.objects.filter(student=student, fee_structure=fee_structure).exists():
                Invoice.objects.create(
                    student=student,
                    fee_structure=fee_structure,
                    amount=fee_structure.amount
                )
                messages.success(request, f"Invoiced {student.get_full_name()} successfully.")
            else:
                messages.warning(request, f"{student.get_full_name()} has already been invoiced.")
            
        return redirect('accounts:migrate-fees')
