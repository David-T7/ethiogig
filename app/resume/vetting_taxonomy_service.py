"""
DB-backed vetting taxonomy: Service → Stack → Skill → Test IDs.
Falls back to vetting_catalog.py when DB rows are missing.
"""
from datetime import timedelta

from django.utils import timezone

from core import models
from .vetting_catalog import (
    MIN_TECHNOLOGIES_TO_PASS,
    stacks_for_position,
    technologies_for_stack,
)

CERTIFICATE_VALIDITY_DAYS = 365


def _serialize_skill(skill, stack_skill=None):
    return {
        'id': str(skill.id),
        'slug': skill.slug,
        'name': skill.name,
        'technology_id': str(skill.technology_id) if skill.technology_id else None,
        'is_required': stack_skill.is_required if stack_skill else True,
        'theoretical_test_id': str(skill.theoretical_test_id) if skill.theoretical_test_id else None,
        'practical_test_id': str(skill.practical_test_id) if skill.practical_test_id else None,
        'content_version': skill.content_version,
        'content_owner': skill.content_owner,
    }


def _serialize_stack(stack, service=None):
    stack_skills = (
        models.StackSkill.objects.filter(stack=stack)
        .select_related('skill')
        .order_by('sort_order', 'skill__name')
    )
    skills = [_serialize_skill(ss.skill, ss) for ss in stack_skills if ss.skill.is_active]
    required_count = sum(1 for s in skills if s['is_required'])
    return {
        'id': str(stack.id),
        'slug': stack.slug,
        'name': stack.name,
        'description': stack.description,
        'skills': skills,
        'required_skill_count': required_count,
        'is_default': (
            models.ServiceVettingStack.objects.filter(service=service, stack=stack, is_default=True).exists()
            if service else False
        ),
    }


def get_service_taxonomy(service):
    if not service:
        return None
    links = (
        models.ServiceVettingStack.objects.filter(service=service, stack__is_active=True)
        .select_related('stack')
        .order_by('-is_default', 'stack__name')
    )
    stacks = [_serialize_stack(link.stack, service) for link in links]
    return {
        'service_id': str(service.id),
        'name': service.name,
        'slug': service.slug,
        'hireable_role_label': service.hireable_role_label or service.name,
        'specialization_tags': service.specialization_tags or [],
        'technologies': [
            {'id': str(t.id), 'name': t.name}
            for t in service.technologies.all()
        ],
        'stacks': stacks,
        'uses_db_taxonomy': bool(stacks),
    }


def get_stacks_for_resume(resume):
    service = resume.applied_position
    if service:
        taxonomy = get_service_taxonomy(service)
        if taxonomy and taxonomy['stacks']:
            return taxonomy['stacks'], taxonomy, True

    position = service.name if service else ''
    legacy = stacks_for_position(position)
    stacks = [
        {
            'id': None,
            'slug': s['slug'],
            'name': s['name'],
            'description': s['description'],
            'skills': [
                {
                    'id': None,
                    'slug': t.lower().replace(' ', '-').replace('.', ''),
                    'name': t,
                    'technology_id': None,
                    'is_required': True,
                    'theoretical_test_id': None,
                    'practical_test_id': None,
                }
                for t in s['technologies']
            ],
            'required_skill_count': MIN_TECHNOLOGIES_TO_PASS,
            'is_default': i == 0,
        }
        for i, s in enumerate(legacy)
    ]
    return stacks, get_service_taxonomy(service) if service else None, False


def resolve_stack(progress, resume):
    if progress.selected_stack_id:
        return progress.selected_stack
    if progress.selected_stack_slug:
        stack = models.VettingStack.objects.filter(slug=progress.selected_stack_slug).first()
        if stack:
            return stack
    return None


def get_stack_skills(stack, progress, resume):
    if stack:
        stack_skills = (
            models.StackSkill.objects.filter(stack=stack)
            .select_related('skill')
            .order_by('sort_order', 'skill__name')
        )
        return [_serialize_skill(ss.skill, ss) for ss in stack_skills if ss.skill.is_active]

    legacy_names = technologies_for_stack(progress.selected_stack_slug, progress.position_name)
    return [
        {
            'id': None,
            'slug': n.lower().replace(' ', '-'),
            'name': n,
            'is_required': True,
            'theoretical_test_id': None,
            'practical_test_id': None,
        }
        for n in legacy_names
    ]


def _result_key(skill):
    return str(skill['id']) if skill.get('id') else skill['name']


def _get_skill_result(results, skill):
    key = _result_key(skill)
    if key in results:
        return results[key]
    return results.get(skill['name'], {})


def _set_skill_result(results, skill, test_kind, payload):
    key = _result_key(skill)
    entry = dict(results.get(key) or results.get(skill['name']) or {})
    entry[test_kind] = payload
    entry['skill_id'] = skill.get('id')
    entry['skill_name'] = skill['name']
    results[key] = entry
    if skill['name'] != key and skill['name'] in results:
        del results[skill['name']]
    return results


def count_passes_by_kind(skills, results, test_kind, required_only=False):
    count = 0
    for skill in skills:
        if required_only and not skill.get('is_required', True):
            continue
        entry = _get_skill_result(results, skill)
        if (entry.get(test_kind) or {}).get('passed'):
            count += 1
    return count


def required_skills_met(skills, results, test_kind):
    required = [s for s in skills if s.get('is_required', True)]
    if not required:
        return count_passes_by_kind(skills, results, test_kind) >= MIN_TECHNOLOGIES_TO_PASS
    for skill in required:
        entry = _get_skill_result(results, skill)
        if not (entry.get(test_kind) or {}).get('passed'):
            return False
    return True


def find_skill_in_stack(stack, progress, resume, technology=None, skill_id=None):
    skills = get_stack_skills(stack, progress, resume)
    if skill_id:
        for s in skills:
            if s.get('id') == str(skill_id):
                return s
    if technology:
        for s in skills:
            if s['name'].lower() == technology.lower():
                return s
    return None


def issue_skill_certificate(resume, skill_obj, stack, theory_entry, practical_entry):
    now = timezone.now()
    expires = now + timedelta(days=CERTIFICATE_VALIDITY_DAYS)
    cert, _ = models.SkillCertificate.objects.update_or_create(
        resume=resume,
        skill=skill_obj,
        stack=stack,
        defaults={
            'theoretical_score': theory_entry.get('score'),
            'practical_score': practical_entry.get('score'),
            'theoretical_submission_id': theory_entry.get('submission_id'),
            'practical_submission_id': practical_entry.get('submission_id'),
            'verified_at': now,
            'expires_at': expires,
            'content_version': skill_obj.content_version,
            'is_active': True,
        },
    )
    return cert


def sync_verified_from_results(progress, stack, resume):
    skills = get_stack_skills(stack, progress, resume)
    verified = []
    results = progress.technology_results or {}
    for skill in skills:
        entry = _get_skill_result(results, skill)
        theory = entry.get('theoretical') or {}
        practical = entry.get('practical') or {}
        if theory.get('passed') and practical.get('passed'):
            verified.append({
                'skill_id': skill.get('id'),
                'name': skill['name'],
                'is_required': skill.get('is_required', True),
                'theoretical_score': theory.get('score'),
                'practical_score': practical.get('score'),
                'stack': progress.selected_stack_slug,
            })
            if skill.get('id') and stack:
                try:
                    skill_obj = models.VettingSkill.objects.get(id=skill['id'])
                    issue_skill_certificate(resume, skill_obj, stack, theory, practical)
                except models.VettingSkill.DoesNotExist:
                    pass
    progress.verified_technologies = verified
    progress.save(update_fields=['verified_technologies', 'updated_at'])
    return verified


def serialize_certificates(resume):
    certs = (
        models.SkillCertificate.objects.filter(resume=resume, is_active=True)
        .select_related('skill', 'stack')
        .order_by('-verified_at')
    )
    return [
        {
            'id': str(c.id),
            'skill_id': str(c.skill_id),
            'skill_name': c.skill.name,
            'stack_name': c.stack.name if c.stack else None,
            'theoretical_score': c.theoretical_score,
            'practical_score': c.practical_score,
            'verified_at': c.verified_at.isoformat(),
            'expires_at': c.expires_at.isoformat(),
            'content_version': c.content_version,
            'expired': c.expires_at <= timezone.now(),
        }
        for c in certs
    ]
