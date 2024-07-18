from celery import shared_task
from django.utils import timezone
from core.models import Dispute

@shared_task
def check_unresolved_disputes():
    now = timezone.now()
    unresolved_disputes = Dispute.objects.filter(status='open', response_deadline__lt=now, auto_resolved=False)
    for dispute in unresolved_disputes:
        dispute.auto_resolved = True
        dispute.save()
