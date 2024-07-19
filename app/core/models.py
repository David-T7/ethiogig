from django.contrib.auth.models import AbstractBaseUser, BaseUserManager ,PermissionsMixin
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from datetime import timedelta



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
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True , null=True)
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
    selected_payment_method = models.JSONField(default=list, blank=True)
    verified = models.BooleanField(default=False ,blank=True)
    REQUIRED_FIELDS = ['first_name','last_name']
    def __str__(self):
        return self.first_name +' '+self.last_name
    
class Client(User):
    company_name = models.CharField(max_length=255, blank=True )
    projects_posted = models.PositiveIntegerField(default=0)
    average_project_budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    preferred_freelancers = models.JSONField(default=list, blank=True)
    verified = models.BooleanField(default=False ,blank=True)
    reviews = models.JSONField(default=list, blank=True)
    REQUIRED_FIELDS = ['company_name'] 
    def __str__(self):
        return self.company_name

class PaymentMethod(models.Model):
    method_name = models.CharField(max_length=50, unique=True)
    details = models.JSONField(default=list, blank=True)  # Store payment details like bank account or PayPal info
    def __str__(self):
        return self.method_name
    

class Project(models.Model):
    client = models.ForeignKey(
        'Client',
        on_delete=models.SET_NULL,
        null=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2 , blank=True , null=True)
    deadline = models.DateTimeField(null=True , blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='open'
    )

    def __str__(self):
        return self.title


class Contract(models.Model):
    client = models.ForeignKey(
        'Client',
        on_delete=models.SET_NULL,
        null=True,
        related_name='contracts'
    )
    freelancer = models.ForeignKey(
        'Freelancer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='contracts'
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        related_name='contracts'
    )
    terms = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    amount_agreed = models.DecimalField(max_digits=10, decimal_places=2 , blank=True , null=True)
    payment_terms = models.TextField(null=True, blank=True)
    freelancer_accepted_terms = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('fully_paid', 'Fully Paid'),
            ('partially_paid', 'Partially Paid'),
            ('failed', 'Failed'),
        ],
        default='not_started'
    )
    
    def __str__(self):
        return f"Contract for {self.project.title} between {self.client.company_name} and {self.freelancer.first_name} {self.freelancer.last_name}"

    def save(self, *args, **kwargs):
        if  self.freelancer_accepted_terms:
            self.status = 'active'
        elif not self.freelancer_accepted_terms:
            self.status = 'pending'
        super().save(*args, **kwargs)
    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError({'end_date': 'End date must be after start date.'})



class Chat(models.Model):
    client = models.ForeignKey('Client',   on_delete=models.SET_NULL, null=True, related_name='chats')
    freelancer = models.ForeignKey('Freelancer',   on_delete=models.SET_NULL, null=True, related_name='chats')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Chat between {self.client} and {self.freelancer}"

class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.SET_NULL, null=True , related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender} at {self.timestamp}"

class Dispute(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('auto_resolved', 'Auto Resolved'),
    ]

    RETURN_CHOICES = [
        ('full', 'Full Refund'),
        ('partial', 'Partial Refund'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    return_type = models.CharField(max_length=10, choices=RETURN_CHOICES)
    return_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, related_name='created_disputes')
    updated_at = models.DateTimeField(auto_now=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, related_name='client_disputes')
    freelancer = models.ForeignKey(Freelancer, on_delete=models.SET_NULL, null=True, related_name='freelancer_disputes')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True)
    response_deadline = models.DateTimeField(default=timezone.now() + timedelta(days=7))
    auto_resolved = models.BooleanField(default=False)
    supporting_documents = models.ManyToManyField('SupportingDocument', blank=True, related_name='related_disputes')

    def save(self, *args, **kwargs):
        if self.auto_resolved:
            self.status = 'auto_resolved'
        super().save(*args, **kwargs)

class SupportingDocument(models.Model):
    file = models.FileField(upload_to='dispute_docs/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    dispute = models.ForeignKey(Dispute, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


