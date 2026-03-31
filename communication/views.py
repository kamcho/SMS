from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notification, PaymentNotification, SMSLog
from core.models import School, Grade, Student
from django.db.models import Q

from .sms_utils import TextSMSAPI
from users.models import MyUser

from django.db.models import Count, Case, When, Value, IntegerField

@login_required
def notification_dashboard(request):
    notifications = Notification.objects.select_related('school', 'grade', 'created_by').annotate(
        success_count=Count(
            Case(When(sms_logs__status='Success', then=Value(1)), output_field=IntegerField())
        ),
        failed_count=Count(
            Case(When(sms_logs__status='Failed', then=Value(1)), output_field=IntegerField())
        )
    ).order_by('-created_at')
    
    # Get recent SMS logs to show failure/success
    sms_logs = SMSLog.objects.select_related('notification').order_by('-timestamp')[:50]
    
    schools = School.objects.all()
    grades = Grade.objects.all()
    
    sms_api = TextSMSAPI()
    sms_balance = sms_api.get_balance()
    
    # Identify recipients
    students_count = Student.objects.filter(studentprofile__status='Active').count()
    guardians_count = MyUser.objects.filter(role='Guardian').count()

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_notification':
            title = request.POST.get('title')
            message = request.POST.get('message')
            target_type = request.POST.get('target_type')
            school_id = request.POST.get('school_id')
            grade_id = request.POST.get('grade_id')
            
            school = School.objects.get(id=school_id) if school_id else None
            grade = Grade.objects.get(id=grade_id) if grade_id else None
            
            notification = Notification.objects.create(
                title=title,
                message=message,
                target_type=target_type,
                school=school,
                grade=grade,
                created_by=request.user
            )
            
            # Identify recipients
            students = Student.objects.filter(studentprofile__status='Active')
            
            if target_type == 'certain_school' and school:
                students = students.filter(studentprofile__school=school)
            elif target_type == 'grade_all_schools' and grade:
                students = students.filter(studentprofile__class_id__grade=grade)
            elif target_type == 'grade_certain_school' and school and grade:
                students = students.filter(studentprofile__school=school, studentprofile__class_id__grade=grade)
            
            # Fetch guardians for these students
            guardians = MyUser.objects.filter(role='Guardian', students__in=students).distinct()
            
            sms_api = TextSMSAPI()
            sent_count = 0
            fail_count = 0
            
            for guardian in guardians:
                if guardian.phone_number:
                    success, info = sms_api.send_sms(guardian.phone_number, message, notification=notification)
                    if success:
                        sent_count += 1
                    else:
                        fail_count += 1
            
            msg = f"Notification created. Sent {sent_count} SMS messages."
            if fail_count > 0:
                msg += f" Failed to send {fail_count} messages."
                messages.warning(request, msg)
            else:
                messages.success(request, msg)
                
            return redirect('communication:dashboard')

    return render(request, 'communication/dashboard.html', {
        'notifications': notifications,
        'sms_logs': sms_logs,
        'sms_balance': sms_balance,
        'students_count': students_count,
        'guardians_count': guardians_count,
        'schools': schools,
        'grades': grades,
        'target_choices': Notification.TARGET_CHOICES
    })

@login_required
def delete_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.delete()
    messages.success(request, "Notification deleted.")
    return redirect('communication:dashboard')

@login_required
def payment_notifications_list(request):
    p_notifications = PaymentNotification.objects.select_related('student', 'payment').order_by('-sent_at')
    return render(request, 'communication/payment_notifications.html', {
        'payment_notifications': p_notifications
    })
