from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core import models
from rest_framework.test import APIClient
from rest_framework import status

CREATE_FREELANCER_URL = reverse('user:createFreelancer')
CREATE_CLIENT_URL = reverse('user:createClient')
class PublicApiTests(TestCase):
    # test the public features of the api
    def setUp(self):
        self.client = APIClient()

    def test_create_freelancer_success(self):
        payload = {
            'email': 'test@gmail.com',
            'password': 'test123',
            'first_name': 'Test user',
            'last_name': 'Test user'
        }
        res = self.client.post(CREATE_FREELANCER_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        freelancer = models.Freelancer.objects.get(email=payload['email'])
        self.assertTrue(freelancer.check_password(payload['password']))
        self.assertNotIn('password', res.data)  # Assuming res.data is the correct response format
    def test_create_client_success(self):
        payload = {
            'email': 'test@gmail.com',
            'password': 'test123',
            'company_name': 'Test user',
        }
        res = self.client.post(CREATE_CLIENT_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        client = models.Client.objects.get(email=payload['email'])
        self.assertTrue(client.check_password(payload['password']))
        self.assertNotIn('password', res.data)  # Assuming res.data is the correct response format
    def test_freelancer_with_email_exits_error(self):
        payload ={
            'email':'test@gmail.com',
            'password':'test123',
            'first_name':'Test user',
            'last_name':'Test user'
        }
        models.Freelancer.objects.create(**payload)
        res = self.client.post(CREATE_FREELANCER_URL , payload)
        self.assertEqual(res.status_code , status.HTTP_400_BAD_REQUEST)
    def test_password_too_short_error(self):
        payload ={
            'email':'test@gmail.com',
            'password':'12',
            'first_name':'Test user',
            'last_name':'Test user'
        }
        res = self.client.post(CREATE_FREELANCER_URL , payload)
        self.assertEqual(res.status_code , status.HTTP_400_BAD_REQUEST)
        user_exits = models.Freelancer.objects.filter(email = payload['email'])
        self.assertFalse(user_exits)