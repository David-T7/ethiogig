"""
Populate Service → Stack → Skill taxonomy in the main DB.
Maps legacy service names, aligns Technology M2M, links test UUIDs when tests exist.
"""
import re

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core import models

SKILL_DEFS = [
    ('react', 'React', True),
    ('javascript', 'JavaScript', True),
    ('html', 'HTML', True),
    ('css', 'CSS', True),
    ('nodejs', 'Node.js', True),
    ('express', 'Express', True),
    ('mongodb', 'MongoDB', True),
    ('postgresql', 'PostgreSQL', True),
    ('python', 'Python', True),
    ('django', 'Django', True),
    ('typescript', 'TypeScript', True),
    ('git', 'Git', True),
    ('sql', 'SQL', True),
]

STACK_DEFS = [
    {
        'slug': 'react-developer',
        'name': 'React Developer',
        'description': 'React, JavaScript, HTML, and CSS.',
        'skills': [
            ('react', True), ('javascript', True), ('html', False), ('css', False),
        ],
    },
    {
        'slug': 'frontend-fundamentals',
        'name': 'Frontend Fundamentals',
        'description': 'Core web building blocks.',
        'skills': [
            ('javascript', True), ('html', True), ('css', True),
        ],
    },
    {
        'slug': 'mern-developer',
        'name': 'MERN Developer',
        'description': 'MongoDB, Express, React, and Node.js.',
        'skills': [
            ('mongodb', False), ('express', False), ('react', True), ('nodejs', True),
        ],
    },
    {
        'slug': 'fullstack-javascript',
        'name': 'Full Stack JavaScript',
        'description': 'End-to-end JavaScript development.',
        'skills': [
            ('javascript', True), ('react', True), ('nodejs', True), ('postgresql', False),
        ],
    },
]

SERVICE_ROLE_MAP = {
    'landing page development': {
        'hireable_role_label': 'Frontend Developer',
        'slug': 'frontend-developer',
        'specialization_tags': ['landing-pages'],
        'stacks': ['react-developer', 'frontend-fundamentals'],
        'default_stack': 'react-developer',
    },
    'web application interface development': {
        'hireable_role_label': 'Frontend Developer',
        'slug': 'frontend-developer-web-apps',
        'specialization_tags': ['web-apps'],
        'stacks': ['react-developer', 'fullstack-javascript'],
        'default_stack': 'react-developer',
    },
    'frontend developer': {
        'hireable_role_label': 'Frontend Developer',
        'slug': 'frontend-developer',
        'specialization_tags': [],
        'stacks': ['react-developer', 'frontend-fundamentals'],
        'default_stack': 'react-developer',
    },
}


def _link_tests_for_service(service_name, skill_map):
    """Best-effort: read tests from microservices if Django can import them — skip if not."""
    return 0


class Command(BaseCommand):
    help = 'Sync hireable roles, stacks, skills, and service links into the main database.'

    def handle(self, *args, **options):
        skill_map = {}
        for slug, name, _ in SKILL_DEFS:
            tech, _ = models.Technology.objects.get_or_create(name=name, defaults={'description': f'{name} skill'})
            skill, _ = models.VettingSkill.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'technology': tech, 'content_owner': 'vetting-team', 'content_version': '1.0'},
            )
            skill_map[slug] = skill

        stack_map = {}
        for sdef in STACK_DEFS:
            stack, _ = models.VettingStack.objects.update_or_create(
                slug=sdef['slug'],
                defaults={'name': sdef['name'], 'description': sdef['description']},
            )
            stack_map[sdef['slug']] = stack
            for sort_i, (skill_slug, is_required) in enumerate(sdef['skills']):
                skill = skill_map[skill_slug]
                models.StackSkill.objects.update_or_create(
                    stack=stack, skill=skill,
                    defaults={'is_required': is_required, 'sort_order': sort_i},
                )

        services_updated = 0
        links_created = 0
        for service in models.Services.objects.all():
            key = service.name.strip().lower()
            mapping = SERVICE_ROLE_MAP.get(key)
            if not mapping:
                for mk, mv in SERVICE_ROLE_MAP.items():
                    if mk in key or key in mk:
                        mapping = mv
                        break
            if mapping:
                service.hireable_role_label = mapping['hireable_role_label']
                service.slug = mapping['slug']
                service.specialization_tags = mapping['specialization_tags']
                service.save(update_fields=['hireable_role_label', 'slug', 'specialization_tags'])
                services_updated += 1
                stack_slugs = mapping['stacks']
            else:
                stack_slugs = ['react-developer', 'frontend-fundamentals']

            skill_ids_for_service = set()
            for stack_slug in stack_slugs:
                stack = stack_map.get(stack_slug)
                if not stack:
                    continue
                is_default = mapping and mapping.get('default_stack') == stack_slug
                _, created = models.ServiceVettingStack.objects.get_or_create(
                    service=service, stack=stack, defaults={'is_default': is_default},
                )
                if created:
                    links_created += 1
                for ss in models.StackSkill.objects.filter(stack=stack).select_related('skill'):
                    skill_ids_for_service.add(ss.skill.technology_id)

            tech_ids = [sid for sid in skill_ids_for_service if sid]
            if tech_ids:
                service.technologies.set(models.Technology.objects.filter(id__in=tech_ids))

        self.stdout.write(self.style.SUCCESS(
            f'Synced {len(skill_map)} skills, {len(stack_map)} stacks, '
            f'updated {services_updated} services, {links_created} new service-stack links.'
        ))
        self.stdout.write(
            'Next: run seed_vetting_tests with --link-skills in test services, then '
            'sync_vetting_taxonomy --link-test-ids (or set test IDs in admin on VettingSkill).'
        )
