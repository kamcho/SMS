from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notification, PaymentNotification
from core.models import School, Grade, Student
from django.db.models import Q

@login_required
def notification_dashboard(request):
    # Get all general notifications
    notifications = Notification.objects.select_related('school', 'grade', 'created_by').order_by('-created_at')
    
    # Filter notifications based on user role and school
    if not request.user.is_superuser and request.user.role != 'Admin':
        # Logic to only show notifications relevant to the user's school/grade can go here
        # For now, we allow management by higher roles
        pass

    schools = School.objects.all()
    grades = Grade.objects.all()
    
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
            
            Notification.objects.create(
                title=title,
                message=message,
                target_type=target_type,
                school=school,
                grade=grade,
                created_by=request.user
            )
            messages.success(request, "Notification sent successfully.")
            return redirect('communication:dashboard')

    return render(request, 'communication/dashboard.html', {
        'notifications': notifications,
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
