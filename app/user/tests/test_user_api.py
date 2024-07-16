from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core import models
from rest_framework.test import APIClient
from rest_framework import status

CREATE_FREELANCER_URL = reverse('user:createFreelancer')
CREATE_CLIENT_URL = reverse('user:createClient')
GET_FREELANCER_URL = reverse('user:getFreelancer')
GET_CLINET_URL = reverse('user:getClient')

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

class PrivateFreelancerApiTests(TestCase):
    """Test API requests that require authentication."""

    def setUp(self):
        self.user = models.Freelancer.objects.create(
            email='test@gmail.com',
            password='test123',
            first_name='Test user',
            last_name='Test user'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    def test_retrieve_profile_success(self):
        """Test retrieving profile for logged in freelnacer ."""
        res = self.client.get(GET_FREELANCER_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['id'],self.user.id,)
        self.assertEqual(res.data['email'] , self.user.email)
    def test_post_me_not_allowed(self):
        """Test POST is not allowed for the me endpoint."""
        res = self.client.post(GET_FREELANCER_URL, {})
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    def test_update_user_profile(self):
        """Test updating the user profile for the authenticated freelancer."""
        payload = {'first_name': 'new name', 'password': 'newpassword123'}

        res = self.client.patch(GET_FREELANCER_URL, payload)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, payload['first_name'])
        self.assertTrue(self.user.check_password(payload['password']))
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class PrivateClientApiTests(TestCase):
    """Test API requests that require authentication."""

    def setUp(self):
        self.user = models.Client.objects.create(
            email='test@gmail.com',
            password='test123',
            company_name='Test Company',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    def test_retrieve_profile_success(self):
        """Test retrieving profile for logged in client ."""
        res = self.client.get(GET_CLINET_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['id'],self.user.id)
        self.assertEqual(res.data['email'], self.user.email)
    def test_post_me_not_allowed(self):
        """Test POST is not allowed for the me endpoint."""
        res = self.client.post(GET_CLINET_URL, {})
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    def test_update_user_profile(self):
        """Test updating the user profile for the authenticated client."""
        payload = {'company_name': 'new comapany name', 'password': 'newpassword123'}

        res = self.client.patch(GET_CLINET_URL, payload)

        self.user.refresh_from_db()
        self.assertEqual(self.user.company_name, payload['company_name'])
        self.assertTrue(self.user.check_password(payload['password']))
        self.assertEqual(res.status_code, status.HTTP_200_OK)