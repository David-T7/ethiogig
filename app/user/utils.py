from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from core import models
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


def generate_password_reset_link(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return f"{settings.FRONTEND_URL}reset-password/{uid}/{token}/"


def send_password_reset_email(user_email):
    try:
        user = models.User.objects.get(email=user_email)
    except models.User.DoesNotExist:
        print(f"No user found with email {user_email}")
        return

    reset_link = generate_password_reset_link(user)
    html_content = f"""
    <html>
        <body>
            <p>Click the following link to reset your password:</p>
            <a href="{reset_link}">{reset_link}</a>
        </body>
    </html>
    """
    text_content = f"Click the following link to reset your password: {reset_link}"
    email_message = EmailMultiAlternatives(
        subject='Password Reset Request',
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
    )
    email_message.attach_alternative(html_content, "text/html")
    try:
        email_message.send(fail_silently=False)
        print(f"Password reset link sent to {user_email}")
    except Exception as e:
        print(f"Error sending password reset email: {e}")
