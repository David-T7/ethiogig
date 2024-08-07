from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin 
from django.utils.translation import gettext_lazy as _
from core.models import User , Freelancer , Client , PaymentMethod

class UserAdmin(BaseUserAdmin):
    # Define the admin page for users
    ordering = ['id']
    list_display = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'user_role', 'account_status')}),
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
    list_display = ['email', 'full_name', 'verified']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('full_name', 'profile_picture', 'bio')}),
        (_('Contact Info'), {'fields': ('phone_number', 'address', 'social_links')}),
        (_('Freelancer Details'), {'fields': ('professional_title', 'skills', 'portfolio', 'experience',
                                              'certifications', 'hourly_rate', 'availability_status',
                                              'preferred_working_hours', 'preferred_communication_channels',
                                              'average_rating', 'reviews', 'languages_spoken',
                                              'selected_payment_method', 'verified')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ['last_login', 'date_joined']

class ClientAdmin(admin.ModelAdmin):
    ordering = ['id']
    list_display = ['email', 'company_name', 'verified']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Client Info'), {'fields': ('company_name', 'contact_person', 'average_project_budget',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ['last_login', 'date_joined']


admin.site.register(User, UserAdmin)
admin.site.register(Freelancer , FreelancerAdmin)
admin.site.register(Client , ClientAdmin)
admin.site.register(PaymentMethod)