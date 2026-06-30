from celery import shared_task
from django.utils import timezone
from .models import FullAssessment, ApplicationOnHold, Dispute, DisputeResponse, Notification
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
    
@shared_task
def auto_resolve_disputes():
    """
    Runs hourly. Two auto-resolution cases:

    1. Dispute has no response past response_deadline → rule in favour of the creator.
    2. DisputeResponse has no counter-response past its deadline → rule in favour of the responder.
    """
    now = timezone.now()

    # ── Case 1: other party never responded to the initial dispute ──────────
    expired_disputes = Dispute.objects.filter(
        status='open',
        got_response=False,
        response_deadline__lte=now,
    )
    for dispute in expired_disputes:
        dispute.status = 'auto_resolved'
        dispute.save(update_fields=['status'])

        _notify_dispute_parties(
            dispute,
            title="Dispute auto-resolved",
            description=(
                f'Dispute "{dispute.title}" was auto-resolved in favour of the filer '
                f'because the other party did not respond within the deadline.'
            ),
        )

    # ── Case 2: response exists but creator never replied past its deadline ──
    expired_responses = DisputeResponse.objects.filter(
        got_response=False,
        response_deadline__lte=now,
        dispute__status='open',
    ).exclude(response='no_response').select_related('dispute')

    for dr in expired_responses:
        dispute = dr.dispute

        if dr.response == 'accepted':
            dispute.status = 'resolved'
        else:
            # rejected / counter_offer with no follow-up → responder wins
            dispute.status = 'auto_resolved'
            dispute.return_type = dr.return_type
            if dr.return_amount is not None:
                dispute.return_amount = dr.return_amount

        dispute.save(update_fields=['status', 'return_type', 'return_amount'])

        _notify_dispute_parties(
            dispute,
            title="Dispute auto-resolved",
            description=(
                f'Dispute "{dispute.title}" was auto-resolved '
                f'because no follow-up was received within the deadline.'
            ),
        )


def _notify_dispute_parties(dispute, title, description):
    for user in [dispute.client, dispute.freelancer]:
        if not user:
            continue
        Notification.objects.create(
            user=user,
            type='alert',
            title=title,
            description=description,
        )
        send_email(
            to_email=user.email,
            subject=title,
            html_content=f"<html><body><p>{description}</p></body></html>",
        )


@shared_task
def remove_expired_holds():
    now = timezone.now()
    expired_holds = ApplicationOnHold.objects.filter(hold_until__lte=now)

    for hold in expired_holds:
        # Email details
        subject = "You can now apply for your desired position!"
        position_name = hold.position.name if hold.position else "the position"
        html_content = f"""
        <html>
            <body>
                <p>Good news! You can now apply for <strong>{position_name}</strong> again.</p>
                <p>Visit our platform to submit your application.</p>
            </body>
        </html>
        """
        
        # Send email
        send_email(hold.email, subject, html_content)
        
        # Delete the hold entry
        hold.delete()