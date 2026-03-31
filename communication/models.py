from django.db import models
from django.conf import settings
from core.models import School, Grade

class Notification(models.Model):
    TARGET_CHOICES = (
        ('all_schools', 'All Schools'),
        ('grade_all_schools', 'Certain Grade (All Schools)'),
        ('certain_school', 'Certain School'),
        ('grade_certain_school', 'Certain Grade (Certain School)'),
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_type = models.CharField(max_length=50, choices=TARGET_CHOICES)
    
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return self.title

class PaymentNotification(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Success', 'Success'),
        ('Failed', 'Failed'),
    )
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='payment_notifications')
    payment = models.ForeignKey('accounts.Payment', on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    sent_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment Notification for {self.student.first_name}"
class SMSLog(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Success', 'Success'),
        ('Failed', 'Failed'),
    )
    
    recipient = models.CharField(max_length=20)
    message = models.TextField()
    response_code = models.CharField(max_length=10, null=True, blank=True)
    response_description = models.TextField(null=True, blank=True)
    message_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Optional link to a broadcast notification
    notification = models.ForeignKey(Notification, on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_logs')
    
    def __str__(self):
        return f"SMS to {self.recipient} - {self.status}"
