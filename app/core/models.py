from django.contrib.auth.models import AbstractBaseUser, BaseUserManager ,PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email,password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser , PermissionsMixin):
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True)
    address = models.CharField(max_length=255, blank=True)
    account_status = models.CharField(max_length=20, default='Active')
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)   
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    objects = UserManager()

    USERNAME_FIELD = 'email'
    def __str__(self):
        return self.email



class Freelancer(User):
    professional_title = models.CharField(max_length=50, blank=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    bio = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    portfolio = models.JSONField(default=list, blank=True)
    experience = models.PositiveIntegerField(default=0)
    certifications = models.JSONField(default=list, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    social_links = models.JSONField(default=dict, blank=True)  # JSON field for social media links
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    availability_status = models.CharField(max_length=20, default='Available')
    preferred_working_hours = models.CharField(max_length=100, blank=True)
    preferred_communication_channels = models.JSONField(default=list, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    reviews = models.JSONField(default=list, blank=True)
    languages_spoken = models.JSONField(default=list, blank=True)
    selected_payment_method = models.ManyToManyField('PaymentMethod', blank=True)
    verified = models.BooleanField(default=False ,blank=True)
    REQUIRED_FIELDS = ['first_name','last_name']
    def __str__(self):
        return self.first_name +' '+self.last_name
    
class Client(User):
    company_name = models.CharField(max_length=255, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    projects_posted = models.PositiveIntegerField(default=0)
    average_project_budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    preferred_freelancers = models.JSONField(default=list, blank=True)
    verified = models.BooleanField(default=False ,blank=True)
    reviews = models.JSONField(default=list, blank=True)
    def __str__(self):
        return self.company_name

class PaymentMethod(models.Model):
    method_name = models.CharField(max_length=50, unique=True)
    details = models.JSONField(default=dict, blank=True)  # Store payment details like bank account or PayPal info
    def __str__(self):
        return self.method_name
    

