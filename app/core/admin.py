from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from core import models

class UserAdmin(BaseUserAdmin):
    # Define the admin page for users
    ordering = ['id']
    list_display = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password','email_verified','verification_token')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'account_status')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ['last_login', 'date_joined']
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')
        }),
    )

class FreelancerAdmin(admin.ModelAdmin):
    ordering = ['id']
    list_display = ['email', 'full_name', 'verified', 'hourly_rate']
    fieldsets = (
        (None, {'fields': ('email',)}),
        (_('Personal Info'), {'fields': ('full_name', 'profile_picture', 'bio', 'phone_number', 'address')}),
        (_('Freelancer Details'), {'fields': ('professional_title', 'skills', 'portfolio', 'experience',
                                              'certifications', 'hourly_rate', 'availability_status',
                                              'preferred_working_hours', 'average_rating', 'reviews',
                                              'languages_spoken', 'selected_payment_method', 'verified')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ['last_login', 'date_joined']
    search_fields = ('full_name', 'email')
    list_filter = ('verified', 'availability_status', 'preferred_working_hours')

class ClientAdmin(admin.ModelAdmin):
    ordering = ['id']
    list_display = ['email', 'company_name', 'verified']
    fieldsets = (
        (None, {'fields': ('email', )}),
        (_('Client Info'), {'fields': ('company_name', 'address', 'phone_number', 'contact_person')}),
        (_('Client Details'), {'fields': ('projects_posted', 'preferred_freelancers', 'average_rating', 'reviews', 'verified')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ['last_login', 'date_joined']
    search_fields = ('company_name', 'email')
    list_filter = ('verified',)

admin.site.register(models.User, UserAdmin)
admin.site.register(models.Freelancer, FreelancerAdmin)
admin.site.register(models.Client, ClientAdmin)
admin.site.register(models.PaymentMethod)
admin.site.register(models.Services)
admin.site.register(models.Technology)
admin.site.register(models.Notification)
admin.site.register(models.Appointment)
admin.site.register(models.Interviewer)
admin.site.register(models.FreelancerInterview)
admin.site.register(models.SkillSearch)
admin.site.register(models.Chat)
admin.site.register(models.Message)
admin.site.register(models.Contract)
admin.site.register(models.Milestone)
admin.site.register(models.Dispute)
admin.site.register(models.CounterOffer)
admin.site.register(models.CounterOfferMilestone)
admin.site.register(models.DrcForwardedDisputes)
admin.site.register(models.DisputeManager)
admin.site.register(models.DrcResolvedDisputes)
admin.site.register(models.FullAssessment)
admin.site.register(models.Field)
admin.site.register(models.ResumeChecker)
admin.site.register(models.Project)
admin.site.register(models.Waitlist)
admin.site.register(models.SignUpList)
admin.site.register(models.ResumeCheck)
