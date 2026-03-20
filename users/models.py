from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

class MyUserManager(BaseUserManager):
    def create_user(self, phone_number, email, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone number field must be set')
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(phone_number=phone_number, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, email, password, **extra_fields)

class MyUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('Teacher', 'Teacher'),
        ('Accountant', 'Accountant'),
        ('Receptionist', 'Receptionist'),
        ('Guardian', 'Guardian'),
    )

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Admin')
    school = models.ForeignKey('core.School',null=True,blank=True, on_delete=models.CASCADE)
    students = models.ManyToManyField('core.Student', blank=True, related_name='guardians')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_exam_manager = models.BooleanField(default=False)
    is_exam_officer = models.BooleanField(default=False)
    is_headteacher = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    objects = MyUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['email']

    def get_full_name(self):
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return self.email
