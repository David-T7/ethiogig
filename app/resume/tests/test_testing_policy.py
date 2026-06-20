from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import ScreeningConfig, Services, VettingPipelineRecord
from resume.testing_policy import (
    serialize_testing_policy,
    skip_ai_screening_for_testing,
    skip_kyc_for_testing,
    surveillance_disabled_for_testing,
)
from resume.views import send_resume_for_screening


class TestingPolicyHelpersTest(TestCase):
    def test_defaults_when_no_config(self):
        ScreeningConfig.objects.all().delete()
        policy = serialize_testing_policy()
        self.assertFalse(policy['skip_ai_screening'])
        self.assertFalse(policy['skip_kyc'])
        self.assertFalse(policy['disable_surveillance'])

    def test_flags_reflect_admin_config(self):
        ScreeningConfig.objects.create(
            skip_ai_screening_for_testing=True,
            skip_kyc_for_testing=True,
            disable_surveillance_for_testing=True,
        )
        self.assertTrue(skip_ai_screening_for_testing())
        self.assertTrue(skip_kyc_for_testing())
        self.assertTrue(surveillance_disabled_for_testing())
        policy = serialize_testing_policy()
        self.assertTrue(policy['skip_ai_screening'])
        self.assertTrue(policy['skip_kyc'])
        self.assertTrue(policy['disable_surveillance'])


class SkipAiScreeningFlowTest(TestCase):
    def setUp(self):
        ScreeningConfig.objects.create(
            skip_ai_screening_for_testing=True,
            skip_kyc_for_testing=True,
        )
        self.service = Services.objects.create(name='Landing Page Development')

    @patch('resume.views.send_email')
    @patch('resume.views.trigger_theoretical_test')
    def test_bypass_advances_to_theoretical(self, mock_trigger, _mock_email):
        from core.models import Resume

        resume = Resume.objects.create(
            full_name='Test Candidate',
            email='bypass@test.example',
            applied_position=self.service,
            is_email_verified=True,
            password='hashed',
            resume_file=SimpleUploadedFile('resume.pdf', b'%PDF-1.4 test'),
        )
        scores = send_resume_for_screening(resume)
        self.assertEqual(scores, [100])

        ai = VettingPipelineRecord.objects.get(resume=resume, stage='ai_screening')
        self.assertEqual(ai.status, 'passed')

        kyc = VettingPipelineRecord.objects.get(resume=resume, stage='kyc')
        self.assertEqual(kyc.status, 'passed')

        mock_trigger.assert_called_once_with(resume)
