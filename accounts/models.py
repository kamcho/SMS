from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid

class FeeStructure(models.Model):
    STUDENT_TYPES = [
        ('day', 'Day Scholar'),
        ('boarder', 'Boarder'),
    ]
    grade = models.ManyToManyField('core.Grade')
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE)
    school = models.ForeignKey('core.School', on_delete=models.CASCADE, null=True, blank=True)
    student_type = models.CharField(max_length=10, choices=STUDENT_TYPES, default='day')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('term', 'school', 'student_type')
    
    def __str__(self):
        term = self.term.name if self.term else ""
        school = self.school.name if self.school else "All Schools"
        return f"{school} - {term} ({self.get_student_type_display()})"

class Structure(models.Model):
    fee = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    order = models.IntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_structures', null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_structures', null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = ('fee', 'order')
        ordering = ['order']

class AdmissionFee(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Admission Fee: {self.amount}"
    class Meta:
        ordering = ['created_at']
        verbose_name = "Admission Fee"
        verbose_name_plural = "Admission Fees"

class AdditionalCharges(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    grades = models.ManyToManyField('core.Grade')
    school = models.ForeignKey('core.School', on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_additional_charges', null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_additional_charges', null=True, blank=True)
    
    def __str__(self):
        return f"Additional Charge: {self.name}"
    class Meta:
        ordering = ['created_at']
        verbose_name = "Additional Charge"
        verbose_name_plural = "Additional Charges"

class Invoice(models.Model):
    """
    Acts as a 'billing' record. When an invoice is created, 
    the student's balance in StudentProfile is incremented.
    """
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, null=True, blank=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    previous_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)
    is_billed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            # Update student balance
            from core.models import StudentProfile
            try:
                profile = StudentProfile.objects.get(student=self.student)
                # Capture previous balance
                self.previous_balance = Decimal(profile.fee_balance)
                
                # Increase balance (billing)
                # Ensure we handle decimals before casting to int
                fee_amount = Decimal(str(self.amount)) if self.amount else Decimal('0')
                profile.fee_balance += int(fee_amount.to_integral_value())
                profile.save()
                
                # Capture current balance
                self.current_balance = Decimal(profile.fee_balance)
            except StudentProfile.DoesNotExist:
                pass
            
        super().save(*args, **kwargs)

    def __str__(self):
        desc = self.description if self.description else "General Billing"
        if self.fee_structure:
            desc = f"{self.fee_structure.term.name} Fees"
        return f"Invoice: {self.student.first_name} - {desc}"

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('Cash', 'Cash'),
        ('Mpesa', 'Mpesa'),
        ('Bank', 'Bank Transfer'),
        ('Cheque', 'Cheque'),
    ]
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    previous_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    date_paid = models.DateField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mpesa_transaction = models.OneToOneField('MpesaTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='fee_payment')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            from core.models import StudentProfile
            profile = StudentProfile.objects.get(student=self.student)
            
            # Capture previous balance
            self.previous_balance = Decimal(profile.fee_balance)
            
            # Update profile balance
            # Ensure we handle decimals before casting to int
            payment_amount = Decimal(str(self.amount)) if self.amount else Decimal('0')
            profile.fee_balance -= int(payment_amount.to_integral_value())
            profile.save()
            
            # Capture current balance after payment
            self.current_balance = Decimal(profile.fee_balance)
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment: {self.student.first_name} - {self.amount}"

class StaffSalary(models.Model):
    staff = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salary_profile')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    salary_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.staff.email} - Balance: {self.salary_balance}"

class StaffPayment(models.Model):
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50, choices=[('Cash', 'Cash'), ('Bank', 'Bank Transfer'), ('Mpesa', 'Mpesa')])
    reference = models.CharField(max_length=100, blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recorded_staff_payments')
    mpesa_transaction = models.OneToOneField('MpesaTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='salary_payment')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            salary_profile, created = StaffSalary.objects.get_or_create(staff=self.staff)
            self.balance_before = salary_profile.salary_balance
            
            # Reduce the balance by the payment amount
            salary_profile.salary_balance -= self.amount
            salary_profile.save()
            
            self.balance_after = salary_profile.salary_balance
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment to {self.staff.email}: {self.amount}"


# M-Pesa Integration Models
class MpesaTransaction(models.Model):
    """Main M-Pesa transaction model to track all transactions"""
    TRANSACTION_TYPES = [
        ('stk_push', 'STK Push (Customer to Business)'),
        ('b2c', 'Business to Customer (B2C)'),
        ('b2b', 'Business to Business (B2B)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # M-Pesa specific fields
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    response_code = models.CharField(max_length=10, blank=True, null=True)
    response_description = models.TextField(blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    transaction_date = models.DateTimeField(blank=True, null=True)
    
    # System fields
    student = models.ForeignKey('core.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='mpesa_transactions')
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant_request_id']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"M-Pesa {self.get_transaction_type_display()}: {self.phone_number} - {self.amount}"


class MpesaCallback(models.Model):
    """Model to store M-Pesa callback data"""
    transaction = models.ForeignKey(MpesaTransaction, on_delete=models.CASCADE, related_name='callbacks')
    callback_type = models.CharField(max_length=20)  # 'success', 'timeout', 'failed'
    raw_data = models.JSONField()  # Store the complete callback data
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Callback for {self.transaction}: {self.callback_type}"


class MpesaAccessToken(models.Model):
    """Model to cache M-Pesa access tokens"""
    token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Token expires at {self.expires_at}"
    
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at
