"""Admin-controlled testing bypasses (ScreeningConfig). Not for production."""

from core import models


def _config():
    return models.ScreeningConfig.objects.first()


def skip_ai_screening_for_testing():
    config = _config()
    return bool(config and config.skip_ai_screening_for_testing)


def skip_kyc_for_testing():
    config = _config()
    return bool(config and config.skip_kyc_for_testing)


def surveillance_disabled_for_testing():
    config = _config()
    return bool(config and config.disable_surveillance_for_testing)


def serialize_testing_policy():
    return {
        'skip_ai_screening': skip_ai_screening_for_testing(),
        'skip_kyc': skip_kyc_for_testing(),
        'disable_surveillance': surveillance_disabled_for_testing(),
    }
