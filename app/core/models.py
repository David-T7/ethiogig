from django.contrib.auth.models import AbstractBaseUser, BaseUserManager ,PermissionsMixin
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
from django.contrib.auth.hashers import make_password

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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    WORKING_HOUR_CHOICES = [
        ('full_time', 'Full time (40 or more hrs/week)'),
        ('part_time', 'Part time (Less than 40 hrs/week)'),
        ('hourly', 'Hourly'),
    ]
    availability_choice = [
         ('avaliable', 'avaliable'),
         ('not avaliable', 'avaliable'),
         ('', 'avaliable'),
    ]
    professional_title = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=30, blank=True)
    bio = models.TextField(blank=True)
    skills = models.JSONField(default=list, null=True ,blank=True)
    prev_work_experience = models.JSONField(default=list, blank=True, null=True)
    portfolio = models.JSONField(default=list, blank=True, null=True)
    experience = models.PositiveIntegerField(default=0, blank=True, null=True)
    certifications = models.JSONField(default=list, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    availability_status = models.CharField(max_length=20, default='Available')
    preferred_working_hours = models.CharField(max_length=20, choices=WORKING_HOUR_CHOICES, blank=True, null=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    reviews = models.JSONField(default=list, blank=True, null=True)
    languages_spoken = models.JSONField(default=list, blank=True, null=True)
    selected_payment_method = models.JSONField(default=list, blank=True, null=True)
    verified = models.BooleanField(default=False, blank=True, null=True)
    REQUIRED_FIELDS = ['full_name']
    def __str__(self):
        return self.full_name

    def delete(self, *args, **kwargs):
        if self.contracts.exists():
            raise ValidationError("Cannot delete freelancer who is involved in a project.")
        super().delete(*args, **kwargs)


class FullAssessment(models.Model):
    assessment_status = [
         ('not_started', 'Not Started'),
         ('pending', 'Pending'),
         ('passed', 'Passed'),
         ('failed','Failed'),
         ('on_hold','On Hold')
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    freelancer = models.ForeignKey('Freelancer', on_delete=models.SET_NULL, null=True)
    finished = models.BooleanField(default=False)
    applied_position = models.ForeignKey('Services' , on_delete=models.SET_NULL, null=True)
    soft_skills_assessment_status = models.CharField(choices=assessment_status , default='not_started')
    depth_skill_assessment_status = models.CharField(choices=assessment_status , default='not_started')
    live_assessment_status = models.CharField(choices=assessment_status , default='not_started')
    project_assessment_status = models.CharField(choices=assessment_status , default='not_started')
    status = models.CharField(choices=assessment_status , default='not_started')
    passed = models.BooleanField(default=False)
    on_hold = models.BooleanField(default=False)
    on_hold_duration = models.DurationField(null=True, blank=True)  # Duration field for hold period
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    new_freelancer = models.BooleanField(default=True)

class Client(User):
    company_name = models.CharField(max_length=255, blank=True )
    contact_person = models.CharField(max_length=255, blank=True )
    projects_posted = models.PositiveIntegerField(default=0 , blank=True , null=True)
    preferred_freelancers = models.JSONField(default=list, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    verified = models.BooleanField(default=False ,blank=True , null=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    selected_payment_method = models.JSONField(default=list, blank=True, null=True)
    reviews = models.JSONField(default=list, blank=True , null=True)
    REQUIRED_FIELDS = ['company_name'] 
    def __str__(self):
        return self.company_name
    def delete(self, *args, **kwargs):
        if self.contracts.exists():
            raise ValidationError("Cannot delete client who is involved in a project.")
        super().delete(*args, **kwargs)

class Interviewer(User):
    TYPE = [
        ('technical', 'Technical'),
        ('soft_skills', 'Soft Skills'),
        ('live_interview', 'Live Interview'),
    ]
    full_name = models.CharField(max_length=100)
    expertise = models.ForeignKey('Services', on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    interviews_per_week = models.IntegerField(default=1)
    max_interviews_per_day = models.IntegerField(default=1)
    # New fields for working hours
    working_hours_start = models.TimeField(default=timezone.now)  # Start time of working hours
    working_hours_end = models.TimeField(default=timezone.now)    # End time of working hours
    type = models.CharField(max_length=20, choices=TYPE , default="technical")
    def __str__(self):
        return f"{self.full_name} - {self.expertise}"

class ResumeChecker(User):
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    def __str__(self):
        return f"{self.full_name} - {self.phone_number}"


class DisputeManager(User):
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    dispute_per_week = models.IntegerField(default=1)
    def __str__(self):
        return f"{self.full_name}"

class DrcForwardedDisputes(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey('Dispute', on_delete=models.SET_NULL, null=True, blank=False)
    dispute_manager = models.ForeignKey('DisputeManager', on_delete=models.SET_NULL, null=True, blank=False)
    solved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DrcResolvedDisputes(models.Model):
    RETURN_CHOICES = [
        ('full', 'Full Refund'),
        ('partial', 'Partial Refund'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drc_forwarded = models.ForeignKey('DrcForwardedDisputes', on_delete=models.SET_NULL, null=True, blank=False)
    return_type = models.CharField(max_length=10, choices=RETURN_CHOICES)
    return_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=False)
    winner = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True,blank=False)
    title = models.CharField(max_length=20 , null=True , blank=True)
    comment = models.TextField(blank=True , null=True)
    created_at = models.DateTimeField(auto_now_add=True)



class PaymentMethod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    method_name = models.CharField(max_length=50, unique=True)
    details = models.JSONField(default=list, blank=True)  # Store payment details like bank account or PayPal info
    def __str__(self):
        return self.method_name
    

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        'Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=False
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100 , null=True,blank=True )
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
    duration = models.CharField(
        max_length=10,
        default='1month',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('accepted', 'accepted'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('canceled', 'Canceled'),
            ('inDispute', 'InDispute'),
        ],
        default='draft'
    )
    milestone_based = models.BooleanField(default=False)
    hourly = models.BooleanField(default=False)
    contract_update = models.ForeignKey(
        'Contract',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
        ],
        default='not_started'
    )

    
    def __str__(self):
        return f"Contract for {self.project.title} between {self.client.company_name}"
    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError({'end_date': 'End date must be after start date.'})
    # def is_escrow_fulfilled(self):
    #     if self.milestone_based:
    #         # For milestone-based contracts, check if all related milestones have their escrow fulfilled
    #         milestones = Milestone.objects.filter(contract = self)
    #         for milestone in milestones:
    #             escrow = Escrow.objects.filter(contract=self, milestone=milestone).first()
    #             if not escrow or escrow.amount < milestone.amount:
    #                 return False
    #         return True
    #     else:
    #         # For full payment contracts, check if the total amount agreed is deposited
    #         return Escrow.objects.get(contract=self).amount >= self.amount_agreed

    # def start_project(self):
    #     if self.is_escrow_fulfilled():
    #         self.status = 'active'
    #         self.save()
    #     else:
    #         raise ValidationError("Escrow is not fulfilled.")

class CounterOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract,
         on_delete=models.SET_NULL,
         null=True,
         blank=True,
        related_name='counter_offers'
    )
    title = models.CharField(max_length=255 , null=True , blank=False)
    proposed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    duration = models.CharField(
        max_length=10,
        default='1month',
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('canceled', 'Canceled'),
        ],
        default='pending'
    )
    milestone_based = models.BooleanField(default=False)
    hourly = models.BooleanField(default=False)




class Escrow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey('Contract', on_delete=models.CASCADE)
    milestone = models.OneToOneField('Milestone', on_delete=models.CASCADE , null=True , blank=True)
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Released', 'Released')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deposit_confirmed = models.BooleanField(blank=True , default=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2 , blank=True , null=True)
    def release(self):
        if self.deposit_confirmed and self.contract.status == 'completed':
            # Handle release logic
            self.status = 'Released'
            if self.milestone:
                self.milestone.payment_status = 'in_progress'
                self.milestone.save()
            else:
                self.contract.payment_status = 'in_progress'
        elif (self.deposit_confirmed and self.contract.status == 'pending' and self.milestone.status == 'completed'): 
            # Handle release logic
            if self.milestone.status == 'completed':
                self.status = 'Released'
                self.milestone.payment_status = 'in_progress'
                self.milestone.save()
            
    def __str__(self):
        return f"Escrow for {self.contract}"



class Milestone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) 
    contract = models.ForeignKey('Contract', on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True , null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateTimeField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    milestone_update = models.ForeignKey(
        'Milestone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'accepted'),
            ('inDsipute', 'InDispute'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
        ],
        default='not_started'
    )

    def __str__(self):
        return self.title

    def clean(self):
        if self.due_date < timezone.now():
            raise ValidationError('Due date cannot be in the past.')


class CounterOfferMilestone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) 
    counter_offer = models.ForeignKey('CounterOffer', on_delete=models.CASCADE, related_name='counter_offers')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True , null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.title


class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) 
    client = models.ForeignKey('Client',   on_delete=models.SET_NULL, null=True, related_name='chats')
    freelancer = models.ForeignKey('Freelancer',   on_delete=models.SET_NULL, null=True, related_name='chats')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Chat between {self.client} and {self.freelancer}"

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey('Chat', on_delete=models.SET_NULL, null=True, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField(blank=True, null=True)  # Text content of the message
    file = models.FileField(upload_to='message_files/', blank=True, null=True)  # File upload field
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    def __str__(self):
        return f"Message from {self.sender} at {self.timestamp}"

def default_deadline():
    return timezone.now() + timedelta(days=7)

class Dispute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('auto_resolved', 'Auto Resolved'),
        ('drc_forwarded' ,'DRC Forwarded' )
    ]

    RETURN_CHOICES = [
        ('full', 'Full Refund'),
        ('partial', 'Partial Refund'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    return_type = models.CharField(max_length=10, choices=RETURN_CHOICES)
    return_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True,blank=False ,related_name='created_disputes')
    updated_at = models.DateTimeField(auto_now=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True,blank=False, related_name='client_disputes')
    freelancer = models.ForeignKey(Freelancer, on_delete=models.SET_NULL, null=True,blank=False, related_name='freelancer_disputes')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True , blank=False)
    milestone = models.ForeignKey(Milestone , on_delete=models.SET_NULL, null=True , blank=False )
    response_deadline = models.DateTimeField(default=default_deadline)
    supporting_documents = models.ManyToManyField('SupportingDocument', blank=True, related_name='related_disputes')
    got_response = models.BooleanField(default=False)

class DisputeResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    RESPONSE_CHOICES = [
        ('no_response', 'No Response'),        
        ('rejected', 'Rejected'),
        ('accepted', 'Accepted'),
        ('counter_offer', 'Counter Offer'),
    ]

    RETURN_CHOICES = [
        ('full', 'Full Refund'),
        ('partial', 'Partial Refund'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    return_type = models.CharField(max_length=10, choices=RETURN_CHOICES)
    return_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True,blank=False ,related_name='created_dispute_responses')
    updated_at = models.DateTimeField(auto_now=True)
    dispute = models.ForeignKey(Dispute, on_delete=models.SET_NULL, null=True,blank=False, related_name='dispute_responses')
    response_deadline = models.DateTimeField(default=default_deadline)
    supporting_documents = models.ManyToManyField('SupportingDocument', blank=True, related_name='related_dispute_responses')
    got_response = models.BooleanField(default=False)
    response = models.CharField(max_length=20, choices=RESPONSE_CHOICES, default='no_response')

class SupportingDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='dispute_docs/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    dispute = models.ForeignKey(Dispute, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


class Resume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=50)
    email = models.EmailField(unique=False)
    applied_positions =  models.ManyToManyField("Services")
    resume_file = models.FileField(upload_to='resumes/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    password = models.CharField(max_length=128 , null=False)  # Password field

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.full_name


class ScreeningResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey("Resume", on_delete=models.SET_NULL , null=True)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    position = models.ForeignKey("Services",on_delete=models.SET_NULL , null=True)
    passed = models.BooleanField()
    comments = models.TextField()
    screened_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return "resume screening result for " + f" score :{self.score} passed:{self.passed}"


class ScreeningConfig(models.Model):
    passing_score_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=70.0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Passing Score Threshold: {self.passing_score_threshold}"


class Technology(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    def __str__(self):
        return self.name

class Services(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True , null=True)
    field = models.ForeignKey('Field',on_delete=models.SET_NULL , null=True )
    technologies = models.ManyToManyField(Technology, related_name='services')
    def __str__(self):
        return self.name

class Field(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True , null=True)
    def __str__(self):
        return self.name
class SkillSearch(models.Model):
    skill_name = models.CharField(max_length=100, unique=True)
    search_count = models.PositiveIntegerField(default=0)
    last_searched_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.skill_name


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=100)  # e.g., 'alert', 'message'
    title = models.CharField(max_length=255)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    data = models.JSONField(default=list)

    def __str__(self):
        return f"{self.title} - {self.user.email}"


class Appointment(models.Model):
    INTERVIEW_TYPE = [
        ('soft_skills_assessment', 'Soft Skills'),        
        ('live_assessment', 'Live Assessment'),
        ('depth_skill_assessment', 'Depth Skill Assessment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    freelancer = models.ForeignKey(Freelancer, on_delete=models.SET_NULL, null=True, related_name='appointments')
    category = models.CharField(max_length=255 , null=True , blank=True)  # Category (e.g., Frontend, Backend, etc.)
    interview_type = models.CharField(max_length=255 ,choices=INTERVIEW_TYPE, default="soft_skills_assessment")  # Type (e.g., soft_skills, live_assessment, etc.)
    skills_passed = models.JSONField(default=list , blank=True)  # List of skills passed as a JSON field
    appointment_date = models.DateTimeField(null=True)  # Appointment date
    appointment_date_options = models.JSONField(default=list, blank=True)  # List of appointment date options
    done = models.BooleanField(default=False)
    def __str__(self):
        return f"Appointment for Freelancer {self.freelancer_id} in {self.category} - {self.appointment_date}"

    class Meta:
        ordering = ['appointment_date']

class FreelancerInterview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interviewer = models.ForeignKey(Interviewer, on_delete=models.SET_NULL, null=True, related_name='interviewer_interviews')
    freelancer = models.ForeignKey(Freelancer, on_delete=models.SET_NULL, null=True, related_name='freelancer_interviews')
    appointment = models.ForeignKey('Appointment', on_delete=models.CASCADE)  # Link to the Appointment
    passed = models.BooleanField(default=False)  # Whether the freelancer passed the interview
    feedback = models.TextField(blank=True, null=True)  # Interviewer's feedback on the interview
    done = models.BooleanField(default=False)
    def __str__(self):
        return f"Interview for Freelancer {self.freelancer_id} with Interviewer {self.interviewer_id}"


