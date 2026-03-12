from django.db import models
from django.conf import settings

# Create your models here.
class School(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    
    def __str__(self):
        return self.name

class ExamMode(models.Model):

    exam = models.ForeignKey('Exam.Exam', on_delete=models.CASCADE, null=True, blank=True)
    active = models.BooleanField(default=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return self.name

class Grade(models.Model):
    choices = (
       ('Play Group', 'Play Group'),
       ('PP1', 'PP1'),
       ('PP2', 'PP2'),
       ('Grade 1', 'Grade 1'),
       ('Grade 2', 'Grade 2'),
       ('Grade 3', 'Grade 3'),
       ('Grade 4', 'Grade 4'),
       ('Grade 5', 'Grade 5'),
       ('Grade 6', 'Grade 6'),
       ('Grade 7', 'Grade 7'),
       ('Grade 8', 'Grade 8'),
       ('Grade 9', 'Grade 9'),
       
    )
    name = models.CharField(max_length=100, choices=choices)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return self.name

class Class(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

class Student(models.Model):
    GENDERS = (
        ('male', 'Male'),
        ('female', 'Female'),
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    adm_no = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    joined_date = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDERS)
    location = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return self.first_name

class StudentProfile(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, null=True, blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    fee_balance = models.IntegerField(default=0)
    discipline = models.IntegerField(default=100)
    
    def __str__(self):
        return self.student.first_name

class AcademicYear(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return str(self.start_date.year)


class Term(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name

class TeacherClassProfile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    subject = models.ForeignKey('Exam.Subject', on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.user} - {self.subject.name} ({self.class_id.name})"

class AttendanceSession(models.Model):
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    date = models.DateField()
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['class_id', 'date']

    def __str__(self):
        return f"{self.class_id.name} - {self.date}"

class StudentAttendance(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Half Day', 'Half Day'),
    )
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Present')
    remarks = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        unique_together = ['session', 'student']

    def __str__(self):
        return f"{self.student.first_name} - {self.status}"

class StudentDiscipline(models.Model):
    SEVERITY_CHOICES = (
        ('Minor', 'Minor'),
        ('Moderate', 'Moderate'),
        ('Severe', 'Severe'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='discipline_records')
    date = models.DateField(auto_now_add=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='Minor')
    description = models.TextField()
    action_taken = models.TextField(blank=True, null=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            try:
                profile = self.student.studentprofile
                if self.severity == 'Minor':
                    profile.discipline -= 5
                elif self.severity == 'Moderate':
                    profile.discipline -= 10
                elif self.severity == 'Severe':
                    profile.discipline -= 20
                
                if profile.discipline < 0:
                    profile.discipline = 0
                profile.save()
            except AttributeError:
                pass

    def __str__(self):
        return f"{self.student.first_name} - {self.severity} Incident"
