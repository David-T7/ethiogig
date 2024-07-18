
from celery import Celery
from celery.schedules import crontab

# Initialize Celery application
app = Celery('project')

# Configure Celery settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Define periodic tasks (beat schedule)
app.conf.beat_schedule = {
    'check-unresolved-disputes-every-hour': {
        'task': 'yourapp.tasks.check_unresolved_disputes',  # Replace with your actual task path
        'schedule': crontab(minute=0, hour='*/1'),  # Runs every hour
    },
}

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
