"""
Link VettingSkill rows to theoretical/practical test UUIDs via test microservice HTTP APIs.
Requires REACT_APP_TEST_URL / PRACTICAL_TEST_URL env vars or docker defaults.
"""
import os
from datetime import datetime, timedelta

import jwt
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from core import models

THEORY_URL = os.environ.get(
    'THEORETICAL_TEST_SERVICE_URL',
    'http://host.docker.internal:8001',
)
PRACTICAL_URL = os.environ.get(
    'PRACTICAL_TEST_SERVICE_URL',
    'http://host.docker.internal:8002',
)


class Command(BaseCommand):
    help = 'Link VettingSkill.theoretical_test_id and practical_test_id from test services.'

    def _service_token(self):
        payload = {
            'user_id': '00000000-0000-0000-0000-000000000001',
            'role': 'candidate',
            'exp': datetime.utcnow() + timedelta(hours=1),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    def handle(self, *args, **options):
        linked_theory = 0
        linked_practical = 0
        headers = {'Authorization': f'Bearer {self._service_token()}'}
        for service in models.Services.objects.all():
            category = service.name
            stacks = models.ServiceVettingStack.objects.filter(service=service).select_related('stack')
            skill_ids = set()
            for link in stacks:
                for ss in models.StackSkill.objects.filter(stack=link.stack).select_related('skill'):
                    skill_ids.add(ss.skill_id)

            for skill in models.VettingSkill.objects.filter(id__in=skill_ids):
                if not skill.theoretical_test_id:
                    try:
                        url = (
                            f'{THEORY_URL}/api/theoretical-tests/by-category/'
                            f'{requests.utils.quote(category)}/technology/{requests.utils.quote(skill.name)}/'
                        )
                        r = requests.get(url, headers=headers, timeout=10)
                        if r.status_code == 200 and r.json().get('id'):
                            skill.theoretical_test_id = r.json()['id']
                            linked_theory += 1
                    except Exception as exc:
                        self.stdout.write(f'Theory link skip {skill.name}@{category}: {exc}')

                if not skill.practical_test_id:
                    try:
                        url = (
                            f'{PRACTICAL_URL}/api/practical-tests/by-category/'
                            f'{requests.utils.quote(category)}/technology/{requests.utils.quote(skill.name)}/'
                        )
                        r = requests.get(url, headers=headers, timeout=10)
                        if r.status_code == 200 and r.json().get('id'):
                            skill.practical_test_id = r.json()['id']
                            linked_practical += 1
                    except Exception as exc:
                        self.stdout.write(f'Practical link skip {skill.name}@{category}: {exc}')

                skill.save(update_fields=['theoretical_test_id', 'practical_test_id', 'updated_at'])

        self.stdout.write(self.style.SUCCESS(
            f'Linked {linked_theory} theoretical and {linked_practical} practical test IDs.'
        ))
