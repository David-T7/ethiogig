import json
import pypdf
import os
import google.generativeai as genai
from django.core.mail import send_mail
from django.conf import settings
from core import models
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
def generate_password_reset_link(user):
    """Generate a password reset link."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_link = f"http://127.0.0.1:8000/reset-password/{uid}/{token}/"
    return reset_link

def send_password_reset_email(user_email):
    """Generate a password reset link and send it to the user's email."""
    try:
        user = models.User.objects.get(email=user_email)
    except models.User.DoesNotExist:
        print(f"No user found with email {user_email}")
        return
    
    reset_link = generate_password_reset_link(user)
    subject = 'Password Reset Request'
    message = f'Click the following link to reset your password: {reset_link}'

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
    )
    print(f"Password reset link sent to {user_email}")