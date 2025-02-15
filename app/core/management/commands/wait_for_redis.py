import time
import redis
from django.core.management.base import BaseCommand
from django.conf import settings
from urllib.parse import urlparse

class Command(BaseCommand):
    """Django command to wait for Redis."""

    def handle(self, *args, **options):
        """Entrypoint for command."""
        self.stdout.write('Waiting for Redis...')
        redis_up = False
        
        # Extract Redis connection parameters from CELERY_BROKER_URL
        redis_url = urlparse(settings.CELERY_BROKER_URL)
        redis_host = redis_url.hostname
        redis_port = redis_url.port
        
        while not redis_up:
            try:
                r = redis.StrictRedis(
                    host=redis_host,
                    port=redis_port,
                    db=0
                )
                r.ping()
                redis_up = True
            except redis.ConnectionError:
                self.stdout.write('Redis unavailable, waiting 1 second...')
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS('Redis available!'))
