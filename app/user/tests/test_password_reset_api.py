from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core import mail
from core.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

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