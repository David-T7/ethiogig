from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
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
        