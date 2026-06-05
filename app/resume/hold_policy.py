from django.utils import timezone

from core import models


def application_holds_enabled():
    """Return False when admin has disabled holds for testing."""
    config = models.ScreeningConfig.objects.first()
    if config and config.disable_application_holds:
        return False
    return True


def active_application_hold(resume):
    """Active ApplicationOnHold for this resume, or None if holds are disabled."""
    if not application_holds_enabled():
        return None
    if not resume.applied_position:
        return None
    return models.ApplicationOnHold.objects.filter(
        email=resume.email,
        position=resume.applied_position,
        hold_until__gt=timezone.now(),
    ).order_by('-hold_until').first()
