from django.db import models
from django.conf import settings
from core.models import Student

class Block(models.Model):
    GENDERS = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('mixed', 'Mixed'),
    )
    name = models.CharField(max_length=100)
    gender_type = models.CharField(max_length=10, choices=GENDERS)
    warden = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} Block"

class Room(models.Model):
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(default=4)
    
    def __str__(self):
        return f"{self.block.name} - Room {self.room_number}"

    @property
    def is_full(self):
        return self.beds.filter(is_occupied=True).count() >= self.capacity

    @property
    def current_occupancy(self):
        return self.beds.filter(is_occupied=True).count()

class Bed(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=10)
    is_occupied = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Bed {self.bed_number} ({self.room})"

class Allocation(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='hostel_allocation')
    bed = models.OneToOneField(Bed, on_delete=models.CASCADE, related_name='allocation')
    allocated_date = models.DateField(auto_now_add=True)
    allocated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.student} -> {self.bed}"
