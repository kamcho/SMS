from django.db import models
from django.conf import settings

class Route(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.name} (KES {self.monthly_fee})"

class Vehicle(models.Model):
    plate_number = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    capacity = models.PositiveIntegerField()
    driver_name = models.CharField(max_length=100)
    driver_phone = models.CharField(max_length=15)
    
    def __str__(self):
        return f"{self.plate_number} - {self.driver_name}"

class TransportAssignment(models.Model):
    student = models.OneToOneField('core.Student', on_delete=models.CASCADE, related_name='transport_assignment')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='assignments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    pickup_point = models.CharField(max_length=200, blank=True, null=True)
    custom_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Override route fee (useful for half months)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.is_active:
            try:
                profile = self.student.studentprofile
                # Use custom_fee if provided, otherwise fallback to route's standard monthly fee
                fee_to_charge = self.custom_fee if self.custom_fee is not None else self.route.monthly_fee
                profile.fee_balance += int(fee_to_charge)
                profile.save()
            except Exception:
                pass

    def __str__(self):
        return f"{self.student.first_name} - {self.route.name}"
