# tests.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from core.models import Chat, Message , Client , Freelancer

User = get_user_model()

CHAT_URL = reverse('user:chat-list')

class PrivateChatApiTests(TestCase):
    """Test the private chat API"""

    def setUp(self):
        self.client_user = Client.objects.create(
            email='client@gmail.com',
            password='test123',
            company_name='Client Company',
        )
        self.freelancer_user = Freelancer.objects.create(
            email='freelancer@gmail.com',
            password='test123',
            full_name='Freelancer',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.client_user)

    def test_create_chat(self):
        """Test creating a chat"""
        payload = {
            'client': self.client_user.id,
            'freelancer': self.freelancer_user.id,
        }
        res = self.client.post(CHAT_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Chat.objects.filter(client=self.client_user).exists())

    def test_create_message(self):
        """Test creating a message in a chat"""
        chat = Chat.objects.create(client=self.client_user, freelancer=self.freelancer_user)
        MESSAGE_URL = reverse('user:chat-messages-list', kwargs={'chat_pk': chat.id})
        payload = {
            'content': 'Hello Freelancer',
        }
        res = self.client.post(MESSAGE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Message.objects.filter(chat=chat).exists())
