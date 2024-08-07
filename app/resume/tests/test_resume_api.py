import os
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Resume, ScreeningResult, ScreeningConfig, Freelancer
from ..utils import extract_text_from_pdf, send_password_reset_email, create_freelancer_from_resume
from django.core import mail
from core.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


class ResumeTests(APITestCase):
    def setUp(self):
        self.resume_data = {
            "full_name": "John Doe",
            "email": "john.doe@example.com",
            "position_applied_for": "Software Engineer",
            'password':"testpass",

        }
        self.resume_file_path = 'resumes/resume.pdf'

    def test_create_resume(self):
        url = reverse('resume-list')
        with open(self.resume_file_path, 'rb') as file:
            data = self.resume_data.copy()
            data["resume_file"] = file
            response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Resume.objects.count(), 1)
        self.assertEqual(Resume.objects.get().full_name, 'John Doe')

    def test_screen_resume(self):
        resume = Resume.objects.create(
            full_name="John Doe",
            email="john.doe@example.com",
            password="testpass",
            position_applied_for="Software Engineer",
            resume_file=self.resume_file_path
        )
        url = reverse('resume-screen', args=[resume.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ScreeningResult.objects.count(), 1)
        self.assertEqual(Freelancer.objects.count(), 1)
        # Verify that an email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Your Resume Screening Result', mail.outbox[0].subject)
        self.assertIn('john.doe@example.com', mail.outbox[0].to)
        # Print email content to the terminal
        print("Email sent to:", mail.outbox[0].to)
        print("Email subject:", mail.outbox[0].subject)
        print("Email body:", mail.outbox[0].body)

    def test_extract_text_from_pdf(self):
        """Test the extract_text_from_pdf function."""
        extracted_text = extract_text_from_pdf(self.resume_file_path)
        # Add assertions based on expected extracted text
        self.assertTrue(len(extracted_text) > 0)

    def test_create_freelancer_from_resume(self):
        """Test creating a freelancer from a resume and sending password reset email."""
        resume = Resume.objects.create(
            full_name="Jane Smith",
            email="jane.smith@example.com",
            password="testpass",
            position_applied_for="Data Scientist",
            resume_file=self.resume_file_path
        )
        create_freelancer_from_resume(resume)
        # Check if freelancer is created
        self.assertEqual(Freelancer.objects.count(), 1)
        freelancer = Freelancer.objects.get(email="jane.smith@example.com")
        self.assertIsNotNone(freelancer)
        self.assertFalse(freelancer.is_active)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='oldpassword'
        )
        self.token = default_token_generator.make_token(self.user)
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.reset_url = reverse('password-reset', args=[self.uid, self.token])

    def test_password_reset_success(self):
        data = {'new_password': 'newpassword'}
        response = self.client.post(self.reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword'))

    def test_password_reset_invalid_token(self):
        invalid_token = 'invalid-token'
        invalid_reset_url = reverse('password-reset', args=[self.uid, invalid_token])
        data = {'new_password': 'newpassword'}
        response = self.client.post(invalid_reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_missing_password(self):
        response = self.client.post(self.reset_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('New password is required', response.data['error'])


    def test_extract_text_from_pdf(self):
        """Test the extract_text_from_pdf function."""
        extracted_text = extract_text_from_pdf(self.resume_file_path)
        # print("Extracted text:", extracted_text)  # Add print statement for debugging


class ScreeningResultTests(APITestCase):
    def test_list_screening_results(self):
        url = reverse('screeningresult-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class ScreeningConfigTests(APITestCase):
    def test_create_screening_config(self):
        url = reverse('screeningconfig-list')
        data = {
            "passing_score_threshold": 75.0
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ScreeningConfig.objects.count(), 1)
        self.assertEqual(ScreeningConfig.objects.get().passing_score_threshold, 75.0)

    def test_update_screening_config(self):
        config = ScreeningConfig.objects.create(passing_score_threshold=70.0)
        url = reverse('screeningconfig-detail', args=[config.id])
        data = {
            "passing_score_threshold": 80.0
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ScreeningConfig.objects.get().passing_score_threshold, 80.0)
    

class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='oldpassword'
        )
        self.token = default_token_generator.make_token(self.user)
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.reset_url = reverse('reset-password', args=[self.uid, self.token])

    def test_password_reset_success(self):
        data = {'new_password': 'newpassword'}
        response = self.client.post(self.reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword'))

    def test_password_reset_invalid_token(self):
        invalid_token = 'invalid-token'
        invalid_reset_url = reverse('reset-password', args=[self.uid, invalid_token])
        data = {'new_password': 'newpassword'}
        response = self.client.post(invalid_reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_missing_password(self):
        response = self.client.post(self.reset_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('New password is required', response.data['error'])


class PasswordResetRequestTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='john.doe@example.com', password='password123')
        self.url = reverse('password-reset-request')
        self.data = {'email': 'john.doe@example.com'}

    def test_password_reset_request(self):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Password Reset Request', mail.outbox[0].subject)
        print("Email sent to:", mail.outbox[0].to)
        print("Email subject:", mail.outbox[0].subject)
        print("Email body:", mail.outbox[0].body)

    def test_password_reset_request_invalid_email(self):
        data = {'email': 'invalid.email@example.com'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)
