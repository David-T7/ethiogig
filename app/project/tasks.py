from celery import shared_task
from django.utils import timezone
from core.models import Dispute , DisputeResponse

@shared_task
def check_unresolved_disputes():
    now = timezone.now()
    unresolved_disputes = Dispute.objects.filter(status='open', response_deadline__lt=now ,got_response=False)
    for dispute in unresolved_disputes:
        dispute.status = "auto_resolved"
        dispute.save()

