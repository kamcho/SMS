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
            
        context['q'] = self.request.GET.get('q', '')
        context['total_staff'] = self.get_queryset().count()
        context['total_unpaid'] = StaffSalary.objects.aggregate(Sum('salary_balance'))['salary_balance__sum'] or 0
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
