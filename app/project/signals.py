from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Contract, Escrow, Milestone


@receiver(post_save, sender=Contract)
def create_escrow_on_acceptance(sender, instance, **kwargs):
    if instance.status != 'accepted':
        return
    if Escrow.objects.filter(contract=instance).exists():
        return

    if instance.milestone_based:
        milestones = Milestone.objects.filter(contract=instance)
        for milestone in milestones:
            Escrow.objects.create(
                contract=instance,
                milestone=milestone,
                amount=milestone.amount,
                status='Pending',
            )
    else:
        Escrow.objects.create(
            contract=instance,
            amount=instance.amount_agreed,
            status='Pending',
        )
