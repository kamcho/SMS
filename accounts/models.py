from django.db import models
from django.conf import settings
from decimal import Decimal

class FeeStructure(models.Model):
    grade = models.ForeignKey('core.Grade', on_delete=models.CASCADE)
    academic_year = models.ForeignKey('core.AcademicYear', on_delete=models.CASCADE)
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('grade', 'academic_year', 'term')

    def __str__(self):
        return f"{self.grade.name} - {self.term.name} ({self.academic_year.start_date.year})"

class Invoice(models.Model):
    """
    Acts as a 'billing' record. When an invoice is created, 
    the student's balance in StudentProfile is incremented.
    """
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_billed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            # Update student balance
            from core.models import StudentProfile
            profile = StudentProfile.objects.get(student=self.student)
            profile.fee_balance += int(self.amount)  # StudentProfile uses IntegerField
            profile.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice: {self.student.first_name} - {self.fee_structure.term.name}"

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
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            from core.models import StudentProfile
            profile = StudentProfile.objects.get(student=self.student)
            
            # Capture previous balance
            self.previous_balance = Decimal(profile.fee_balance)
            
            # Update profile balance
            profile.fee_balance -= int(self.amount)
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
