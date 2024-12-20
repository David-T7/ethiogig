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
from django.contrib.auth.tokens import default_token_generator
from django.utils.crypto import get_random_string
from rest_framework.decorators import action
from core import models
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
def generate_password_reset_link(user):
    """Generate a password reset link."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_link = f"{settings.FRONTEND_URL}reset-password/{uid}/{token}/"
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


def send_password_reset_email(to_email):
    """Generate a password reset link and send it to the user's email."""
    try:
        user = models.User.objects.get(email=to_email)
    except models.User.DoesNotExist:
        print(f"No user found with email {to_email}")
        return
    
    reset_link = generate_password_reset_link(user)
    subject = 'Password Reset Request'
    # HTML content for the email
    html_content = f"""
    <html>
        <body>
            <p>Click the following link to reset your password::</p>
            <a href="{reset_link}">{reset_link}</a>
        </body>
    </html>
    """
    message = f'Click the following link to reset your password: {reset_link}'
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content = html_content
    )
    print("from email is",settings.DEFAULT_FROM_EMAIL)
    print("api key is ",settings.EMAIL_HOST_USER)
    print("message is ",message)
    try:
        sg = SendGridAPIClient(settings.EMAIL_HOST_USER)
        response = sg.send(message)
        print("email sent")
        return response.status_code
    except Exception as e:
        print("error sending email ",str(e))
        return str(e)