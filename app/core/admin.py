from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from core.models import (User, Freelancer, Client, PaymentMethod, Services, 
Technology , Notification , Appointment , Interviewer , FreelancerInterview)

class UserAdmin(BaseUserAdmin):
    # Define the admin page for users
    ordering = ['id']
    list_display = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
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

admin.site.register(User, UserAdmin)
admin.site.register(Freelancer, FreelancerAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(PaymentMethod)
admin.site.register(Services)
admin.site.register(Technology)
admin.site.register(Notification)
admin.site.register(Appointment)
admin.site.register(Interviewer)
admin.site.register(FreelancerInterview)