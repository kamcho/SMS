from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class Route(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    one_way_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    round_trip_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.name} (OW: {self.one_way_fee} | RT: {self.round_trip_fee})"

class Vehicle(models.Model):
    plate_number = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    capacity = models.PositiveIntegerField()
    driver_name = models.CharField(max_length=100)
    driver_phone = models.CharField(max_length=15)
    
    def __str__(self):
        return f"{self.plate_number} - {self.driver_name}"

class TransportAssignment(models.Model):
    TRIP_TYPES = [
        ('one_way', 'One Way'),
        ('round_trip', 'Round Trip'),
    ]
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='transport_assignments')
    academic_year = models.ForeignKey('core.AcademicYear', on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE, null=True, blank=True)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='assignments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPES, default='round_trip')
    pickup_point = models.CharField(max_length=200, blank=True, null=True)
    custom_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Override standard fee")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent multiple active assignments for the same student in the same term
        unique_together = ('student', 'academic_year', 'term', 'is_active')
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'academic_year', 'term'],
                condition=models.Q(is_active=True),
                name='unique_active_assignment_per_term'
            )
        ]
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        should_bill = False
        
        if is_new:
            should_bill = True
        else:
            # For updates, we always bill as requested, but let's avoid double billing within 15 seconds
            from accounts.models import Invoice
            
            last_transport_bill = Invoice.objects.filter(
                student=self.student,
                description__icontains='Transport'
            ).order_by('-created_at').first()
            
            if not last_transport_bill or (timezone.now() - last_transport_bill.created_at) > timedelta(seconds=15):
                should_bill = True

        super().save(*args, **kwargs)
        
        if should_bill and self.is_active:
            # Use custom_fee if provided, otherwise fallback to route's standard fee based on trip_type
            if self.custom_fee is not None:
                fee_to_charge = self.custom_fee
            else:
                fee_to_charge = self.route.one_way_fee if self.trip_type == 'one_way' else self.route.round_trip_fee
            
            # Create an invoice
            from accounts.models import Invoice
            Invoice.objects.create(
                student=self.student,
                amount=fee_to_charge,
                description=f"Transport: {self.route.name} ({self.get_trip_type_display()})"
            )

    def __str__(self):
        return f"{self.student.first_name} - {self.route.name}"
