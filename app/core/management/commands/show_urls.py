from django.core.management.base import BaseCommand
from django.urls import get_resolver

class Command(BaseCommand):
    help = 'Displays all URLs in the project'

    def handle(self, *args, **kwargs):
        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        def list_urls(lpatterns, parent_pattern=''):
            for pattern in lpatterns:
                if hasattr(pattern, 'url_patterns'):
                    # Recursively list URLs if it's an include()
                    list_urls(pattern.url_patterns, parent_pattern + str(pattern.pattern))
                else:
                    self.stdout.write(parent_pattern + str(pattern.pattern))

        list_urls(url_patterns)
