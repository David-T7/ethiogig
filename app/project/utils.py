from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def send_email(to_email, subject, html_content):
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return 200
    except Exception as e:
        print("error sending email", str(e))
        return str(e)
        