"""Admin-controlled testing bypasses (ScreeningConfig). Not for production."""

from core import models


def _config():
    return models.ScreeningConfig.objects.first()


def skip_email_verification_for_testing():
    config = _config()
    return bool(config and config.skip_email_verification_for_testing)


def skip_ai_screening_for_testing():
    config = _config()
    return bool(config and config.skip_ai_screening_for_testing)


def skip_kyc_for_testing():
    config = _config()
    return bool(config and config.skip_kyc_for_testing)


def surveillance_disabled_for_testing():
    config = _config()
    return bool(config and config.disable_surveillance_for_testing)


def manual_proctoring_required():
    config = _config()
    return bool(config and config.require_manual_proctoring)


def serialize_testing_policy():
    return {
        'skip_email_verification': skip_email_verification_for_testing(),
        'skip_ai_screening': skip_ai_screening_for_testing(),
        'skip_kyc': skip_kyc_for_testing(),
        'disable_surveillance': surveillance_disabled_for_testing(),
    }
