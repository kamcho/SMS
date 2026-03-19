from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.db import transaction as django_transaction
from django.utils import timezone
from .models import Payment, FeeStructure, Invoice, StaffSalary, StaffPayment, Structure, MpesaTransaction
from core.models import School, Student, StudentProfile
from users.models import MyUser
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
import json
from datetime import datetime, timedelta
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from django.views.generic import DetailView
from .mpesa_transaction_service import MpesaTransactionService
from .mpesa_service import MpesaService

class FeeStructureDetailView(LoginRequiredMixin, DetailView):
    model = FeeStructure
    template_name = 'accounts/fee_structure_detail.html'
    context_object_name = 'fee_structure'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['structures'] = Structure.objects.filter(fee=self.object).order_by('order')
        return context

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
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not request.user.is_superuser and request.user.role != 'Admin' and request.user.role != 'Accountant':
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
            messages.error(request, "Permission denied.")
            return redirect('accounts:migrate-fees')

        action = request.POST.get('action')
        grade_id = request.POST.get('grade_id')
        
        def get_redirect_url():
            url = reverse('accounts:migrate-fees')
            if grade_id:
                url += f"?grade={grade_id}"
            return url
        
        from core.models import Term, AcademicYear
        active_term = Term.objects.filter(is_active=True).first()
        active_year = AcademicYear.objects.filter(is_active=True).first()
        
        if not active_term or not active_year:
            msg = "No active term/year set."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg})
            messages.error(request, msg)
            return redirect(get_redirect_url())
            
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
                msg = f"No fee structure found for {student.get_full_name()} (School: {student.profile.school.name}, Type: {'Boarder' if student.is_boarder else 'Day Scholar'})."
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': msg})
                messages.error(request, msg)
                return redirect(get_redirect_url())

            if not Invoice.objects.filter(student=student, fee_structure=fee_structure).exists():
                Invoice.objects.create(
                    student=student,
                    fee_structure=fee_structure,
                    amount=fee_structure.amount
                )
                msg = f"Invoiced {student.get_full_name()} successfully."
                if is_ajax:
                    return JsonResponse({'status': 'success', 'message': msg})
                messages.success(request, msg)
            else:
                msg = f"{student.get_full_name()} has already been invoiced."
                if is_ajax:
                    return JsonResponse({'status': 'info', 'message': msg})
                messages.warning(request, msg)
            
            if is_ajax:
                return JsonResponse({'status': 'success'})
            
        return redirect(get_redirect_url())

class MigrateTermView(LoginRequiredMixin, TemplateView):
    """
    Invoices all students across all schools for a selected term
    based on the fee structure of their grade and student type.
    """
    template_name = 'accounts/migrate_term.html'

    def get_context_data(self, **kwargs):
        from core.models import Term
        context = super().get_context_data(**kwargs)

        profiles = StudentProfile.objects.select_related('student', 'class_id__grade', 'school')

        context['terms'] = Term.objects.all().order_by('id')
        context['total_students'] = profiles.count()
        context['schools'] = School.objects.all()

        return context

    def post(self, request, *args, **kwargs):
        from core.models import Term
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not request.user.is_superuser and request.user.role not in ['Admin', 'Accountant']:
            msg = "Permission denied."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg}, status=403)
            messages.error(request, msg)
            return redirect('accounts:migrate-term')

        term_id = request.POST.get('term_id')
        if not term_id:
            msg = "Please select a term to migrate."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg})
            messages.error(request, msg)
            return redirect('accounts:migrate-term')

        try:
            selected_term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            msg = "Selected term does not exist."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg})
            messages.error(request, msg)
            return redirect('accounts:migrate-term')

        profiles = StudentProfile.objects.select_related('student', 'class_id__grade', 'school')

        def get_structure_for_profile(profile):
            s_type = 'boarder' if profile.student.is_boarder else 'day'
            return FeeStructure.objects.filter(
                term=selected_term,
                school=profile.school,
                student_type=s_type,
                grade=profile.class_id.grade,
            ).first()

        invoice_count = 0
        missing_structure_count = 0

        for profile in profiles:
            fee_structure = get_structure_for_profile(profile)
            if not fee_structure:
                missing_structure_count += 1
                continue

            if not Invoice.objects.filter(student=profile.student, fee_structure=fee_structure).exists():
                Invoice.objects.create(
                    student=profile.student,
                    fee_structure=fee_structure,
                    amount=fee_structure.amount,
                )
                invoice_count += 1

        msg = f"Successfully created {invoice_count} invoices across all schools for {selected_term.name}."
        if missing_structure_count > 0:
            msg += f" {missing_structure_count} students skipped due to missing fee structures."

        if is_ajax:
            return JsonResponse({'status': 'success', 'message': msg})

        messages.success(request, msg)
        return redirect('accounts:migrate-term')
@login_required
def payments_list_view(request):
    """View that calls M-Pesa Pull Transactions API for reconciliation"""
    print("🎯 DEBUG: Payments list view (Pull API) called!")
    
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    mpesa_service = MpesaService()
    
    # Get filters from request
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    offset = request.GET.get('offset', 0)
    
    # Format dates as required by Daraja: YYYY-MM-DD HH:MM:SS
    if not date_from:
        # Default to last 48 hours as per Daraja Pull API capability
        start_date = (timezone.localtime() - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
    else:
        start_date = f"{date_from} 00:00:00"
        
    now_time = timezone.localtime()
    if not date_to:
        end_date = now_time.strftime('%Y-%m-%d %H:%M:%S')
    else:
        # If the user selected today or a future date, cap it at 'now'
        # Otherwise use the end of the selected day.
        try:
            match_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            if match_date >= now_time.date():
                end_date = now_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                end_date = f"{date_to} 23:59:59"
        except:
            end_date = now_time.strftime('%Y-%m-%d %H:%M:%S')

        # Call the service
    from datetime import datetime, timedelta

    # adjust for 3-hour difference (data source ahead of you)
    now_adjusted = datetime.now() + timedelta(hours=3)
    end_date = now_adjusted
    start_date = now_adjusted - timedelta(hours=48)
    
    result = mpesa_service.query_pull_transactions(
        start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
        end_date=end_date.strftime('%Y-%m-%d %H:%M:%S'),
        offset=offset
    )
    
    transactions = []
    if result.get('success'):
        data = result.get('data', {})
        
        # Based on Documentation: Response Parameter Definition 2. Query Pull Transaction
        # Successful response usually contains a 'Transaction' field which is a list
        # Error 1001 says: "Transaction": "[[]]"
        
        # Safaricom uses different field names: 'Response' in some versions, 'Transaction' in others
        raw_transactions = data.get('Response') or data.get('Transaction')
        
        # If it's a string representation of a list, try to parse it (sometimes Safaricom APIs do this)
        if isinstance(raw_transactions, str):
            try:
                import json
                raw_transactions = json.loads(raw_transactions)
            except:
                pass

        if isinstance(raw_transactions, list):
            # Handle list of lists or list of dicts: [[{...}]] or [{...}]
            for entry in raw_transactions:
                # Flatten one level if needed
                items_to_process = entry if isinstance(entry, list) else [entry]
                
                for item in items_to_process:
                    if not item:
                        continue
                        
                    if isinstance(item, dict):
                        receipt = item.get('transactionId')
                        phone = item.get('msisdn')
                        amount = item.get('amount')
                        date_str = item.get('trxDate')
                        
                        # Save to database if not exists
                        txn = None
                        processed = False
                        if receipt:
                            txn, created = MpesaTransaction.objects.get_or_create(
                                mpesa_receipt_number=receipt,
                                defaults={
                                    'transaction_type': 'stk_push',
                                    'phone_number': phone,
                                    'amount': amount,
                                    'status': 'completed',
                                    'response_code': '0',
                                    'response_description': 'Pulled from Daraja API',
                                    'processed_at': timezone.now()
                                }
                            )
                            processed = hasattr(txn, 'fee_payment') or hasattr(txn, 'salary_payment')
                            if created and date_str:
                                try:
                                    # Pull API date format is usually YYYY-MM-DD HH:MM:SS or ISO 8601
                                    try:
                                        parsed_date = datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
                                    except ValueError:
                                        parsed_date = parse_datetime(str(date_str))
                                        if parsed_date:
                                            # If it has tzinfo, make it naive or vice versa depending on settings
                                            # For simplicity, we'll strip tz if it's there
                                            if hasattr(parsed_date, 'replace'):
                                                parsed_date = parsed_date.replace(tzinfo=None)
                                    
                                    if parsed_date:
                                        # Add 3 hours to account for server time difference (EAT is UTC+3)
                                        adjusted_date = parsed_date + timedelta(hours=3)
                                        txn.transaction_date = adjusted_date
                                        txn.save()
                                except Exception:
                                    pass

                        transactions.append({
                            'id': receipt,
                            'phone_number': phone,
                            'amount': amount,
                            'reference_number': receipt,
                            'transaction_date': date_str,
                            'type': item.get('transactiontype'),
                            'account': item.get('billreference'),
                            'organization': item.get('organizationname'),
                            'api_response': item,
                            'saved': True if txn else False,
                            'processed': processed
                        })
                    elif isinstance(item, list) and len(item) >= 6:
                        receipt = item[0]
                        date_str = item[1]
                        phone = item[2]
                        amount = item[5]
                        
                        # Save to database if not exists
                        txn = None
                        processed = False
                        if receipt:
                            txn, created = MpesaTransaction.objects.get_or_create(
                                mpesa_receipt_number=receipt,
                                defaults={
                                    'transaction_type': 'stk_push',
                                    'phone_number': phone,
                                    'amount': amount,
                                    'status': 'completed',
                                    'response_code': '0',
                                    'response_description': 'Pulled from Daraja API',
                                    'processed_at': timezone.now()
                                }
                            )
                            processed = hasattr(txn, 'fee_payment') or hasattr(txn, 'salary_payment')
                            if created and date_str:
                                try:
                                    # from django.utils.dateparse import parse_datetime # Removed duplicate import
                                    try:
                                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                                    except ValueError:
                                        parsed_date = parse_datetime(str(date_str))
                                        if parsed_date and hasattr(parsed_date, 'replace'):
                                            parsed_date = parsed_date.replace(tzinfo=None)
                                    
                                    if parsed_date:
                                        # Adjust for EAT (UTC+3)
                                        txn.transaction_date = parsed_date + timedelta(hours=3)
                                        txn.save()
                                except Exception:
                                    pass

                        transactions.append({
                            'id': receipt,
                            'transaction_date': date_str,
                            'phone_number': phone,
                            'type': item[3],
                            'account': item[4],
                            'amount': amount,
                            'organization': item[6] if len(item) > 6 else '',
                            'api_response': item,
                            'saved': True if txn else False,
                            'processed': processed
                        })
        
        # Check if individual fields are at the root
        elif data.get('transactionId'):
            receipt = data.get('transactionId')
            phone = data.get('msisdn')
            amount = data.get('amount')
            date_str = data.get('trxDate')
            
            txn = None
            processed = False
            if receipt:
                txn, created = MpesaTransaction.objects.get_or_create(
                    mpesa_receipt_number=receipt,
                    defaults={
                        'transaction_type': 'stk_push',
                        'phone_number': phone,
                        'amount': amount,
                        'status': 'completed',
                        'response_code': '0',
                        'response_description': 'Pulled from Daraja API',
                        'processed_at': timezone.now()
                    }
                )
                processed = hasattr(txn, 'fee_payment') or hasattr(txn, 'salary_payment')
                if created and date_str:
                    try:
                        try:
                            parsed_date = datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            parsed_date = parse_datetime(str(date_str))
                            if parsed_date and hasattr(parsed_date, 'replace'):
                                parsed_date = parsed_date.replace(tzinfo=None)
                        
                        if parsed_date:
                            # Adjust for EAT (UTC+3)
                            txn.transaction_date = parsed_date + timedelta(hours=3)
                            txn.save()
                    except Exception:
                        pass

            transactions.append({
                'id': receipt,
                'phone_number': phone,
                'amount': amount,
                'reference_number': receipt,
                'transaction_date': date_str,
                'type': data.get('transactiontype'),
                'account': data.get('billreference'),
                'organization': data.get('organizationname'),
                'api_response': data,
                'saved': True,
                'processed': processed
            })

    # Sort transactions by recent first
    from django.utils.dateparse import parse_datetime
    def get_sort_date(txn):
        date_str = txn.get('transaction_date')
        if date_str:
            try:
                dt = datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
                return dt
            except ValueError:
                parsed = parse_datetime(str(date_str))
                if parsed:
                    return parsed.replace(tzinfo=None)
                try:
                    return datetime.strptime(str(date_str), '%Y%m%d%H%M%S')
                except ValueError:
                    pass
        return datetime.min

    transactions.sort(key=get_sort_date, reverse=True)

    context = {
        'result': result,
        'success': result.get('success', False),
        'transactions': transactions,
        'error': result.get('error'),
        'status_code': result.get('status_code'),
        'total_count': len(transactions),
        'raw_response': result.get('data', {}),
        'date_from': date_from,
        'date_to': date_to,
        'offset': offset,
        # Specific Daraja fields
        'response_ref_id': result.get('data', {}).get('ResponseRefID') or result.get('data', {}).get('RequestID'),
        'response_code': result.get('data', {}).get('ResponseCode'),
        'response_message': result.get('data', {}).get('ResponseMessage'),
    }
    
    return render(request, 'accounts/payments_list.html', context)

@login_required
def payments_api_view(request):
    """API endpoint for payments data"""
    mpesa_service = MpesaService()
    mpesa_service = MpesaTransactionService()
    
    if request.method == 'GET':
        # Get transactions with filters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        phone_number = request.GET.get('phone_number')
        reference = request.GET.get('reference')
        status = request.GET.get('status')
        
        # Parse dates
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                start_date = None
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                end_date = None
        
        transactions = mpesa_service.search_transactions(
            phone_number=phone_number,
            reference=reference,
            start_date=start_date,
            end_date=end_date,
            status=status
        )
        
        return JsonResponse({
            'success': True,
            'transactions': transactions,
            'total_count': len(transactions)
        })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required
def get_student_by_id(request, student_id):
    """Fetch student details by id for M-Pesa reconciliation"""
    from core.models import Student
    try:
        # Search for student with matching id
        student = Student.objects.get(id=student_id)
        profile = student.studentprofile
        return JsonResponse({
            'success': True,
            'student': {
                'id': student.id,
                'full_name': student.get_full_name(),
                'adm_no': student.adm_no,
                'fee_balance': profile.fee_balance
            }
        })
    except (Student.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def process_pulled_payment(request):
    """Confirm and process a pulled M-Pesa transaction as a fee payment"""
    try:
        data = json.loads(request.body)
        txn_receipt = data.get('receipt')
        student_id = data.get('student_id')
        amount_val = data.get('amount')
        
        if not all([txn_receipt, student_id, amount_val]):
            return JsonResponse({'success': False, 'error': 'Missing required data'}, status=400)
            
        amount = Decimal(str(amount_val))

        from core.models import Student
        from .models import Payment, MpesaTransaction

        student = Student.objects.get(id=student_id)
        txn = MpesaTransaction.objects.get(mpesa_receipt_number=txn_receipt)

        # Check if already linked via fee_payment or salary_payment
        if hasattr(txn, 'fee_payment'):
             return JsonResponse({'success': False, 'error': 'Transaction already processed as fee payment'}, status=400)
             
        if hasattr(txn, 'salary_payment'):
             return JsonResponse({'success': False, 'error': 'Transaction already processed as salary payment'}, status=400)

        with django_transaction.atomic():
            # Create payment record
            # Note: Payment model's save() method automatically handles fee_balance deduction
            # and captures previous/current balance.
            payment = Payment.objects.create(
                student=student,
                amount=amount,
                method='Mpesa',
                reference=txn_receipt,
                mpesa_transaction=txn,
                date_paid=timezone.now().date(),
                recorded_by=request.user
            )

            # Re-fetch profile to get updated balance from model save()
            profile = student.studentprofile
            
            return JsonResponse({
                'success': True, 
                'message': f'Payment of KES {amount} processed for {student.get_full_name()}. New balance: {profile.fee_balance}'
            })

    except (Student.DoesNotExist, MpesaTransaction.DoesNotExist) as e:
        return JsonResponse({'success': False, 'error': f"Object not found: {str(e)}"}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)