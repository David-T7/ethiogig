from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Setup periodic tasks'

    def handle(self, *args, **kwargs):
        # Create or update a crontab schedule for midnight execution
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="0",
            day_of_week="*",   # Runs every day
            day_of_month="*",  # Runs every month
            month_of_year="*", # Runs every year
        )

        # Task 1: Update expired holds
        PeriodicTask.objects.update_or_create(
            name='update_expired_holds',
            defaults={
                'task': 'core.tasks.update_expired_holds',
                'crontab': schedule,
                'enabled': True,
            }
        )

        # Task 2: Remove expired application holds
        PeriodicTask.objects.update_or_create(
            name='remove_expired_holds',
            defaults={
                'task': 'core.tasks.remove_expired_holds',
                'crontab': schedule,
                'enabled': True,
            }
        )

        logger.info("Periodic tasks 'update_expired_holds' and 'remove_expired_holds' have been set up")
        self.stdout.write(self.style.SUCCESS('Periodic tasks setup successfully!'))
