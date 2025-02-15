from celery import shared_task
from django.utils import timezone
from .models import FullAssessment
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings



def send_email(to_email, subject, html_content):
    print("to email is ",to_email)
    print("subject is ",subject)
    print("html_content is ",html_content)
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
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



@shared_task
def update_expired_holds():
    now = timezone.now()
    assessments = FullAssessment.objects.filter(on_hold=True, hold_until__lte=now)
    
    for assessment in assessments:
        assessment.on_hold = False
        assessment.status = "pending"  # Move back to pending
        assessment.hold_until = None  # Clear the hold date
        assessment.save()
        subject = "Assesment open for submission!"
        notification_description = f"Your assessment {assessment.applied_position.name} is now open for submissions."
        # HTML content for the email
        html_content = f"""
        <html>
            <body>
                <p>{notification_description}</p>
            </body>
        </html>
        """
        
        # Call send_email function with the recipient email, subject, and HTML content
        send_email(assessment.freelancer.email, subject, html_content)
    
