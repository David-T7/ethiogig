from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from core import models
class ModelTest(TestCase):
    def test_create_user_with_email_successful(self):
        email = "test@gmail.com"
        password = 'testpass234'
        user = get_user_model().objects.create_user(
            email = email ,
            password = password
        )
        self.assertEqual(user.email , email)
        self.assertTrue(user.check_password(password))
    def test_new_user_email_normalized(self):
        sample_emails = [
            ['test1@EXAMPLE.com' , 'test1@example.com'  ],
            ['Test2@EXAMPLE.com' , 'Test2@example.com'  ],
            ['TEST3@EXAMPLE.com' , 'TEST3@example.com'  ],
            ['test4@example.com' , 'test4@example.com'  ],
            
        ]
        for email , expected_email in sample_emails:
            user = get_user_model().objects.create_user(email = email , password ="test123pass")
            self.assertEqual(user.email , expected_email)
    def test_new_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('','test123')
    def test_create_super_user(self):
        user = get_user_model().objects.create_superuser(
            email = "superuser@gmail.com",
            password = "test123"
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
    def test_create_freelancer(self):
        freelancer = models.Freelancer.objects.create(
            email = "testuser@gmail.com",
            password = "test123",
            first_name = "Dawit",
            last_name="Tesfaye",
        )
        self.assertEqual(freelancer.first_name +' '+freelancer.last_name , str(freelancer))
    def test_create_client(self):
        client = models.Client.objects.create(
            email = "testuser@gmail.com",
            password = "test123",
            company_name = "Ebs"
        )
        self.assertEqual(client.company_name , str(client))
    