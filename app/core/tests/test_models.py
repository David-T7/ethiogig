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
    def test_Create_Project(self):
        client = models.Client.objects.create(
            email = "testuser@gmail.com",
            password = "test123",
            company_name = "Ebs"
        )
        project = models.Project.objects.create(
            client = client,
            title = "Web Developer",
            description ="We want a react developer"
        )
        self.assertEqual(project.title , str(project))
        self.assertEqual(project.client, client)
        self.assertEqual(project.status, 'open')
    def test_project_exists_after_client_deleted(self):
        client = models.Client.objects.create(
            email="testuser@gmail.com",
            password="test123",
            company_name="Ebs"
        )
        project = models.Project.objects.create(
            client=client,
            title="Web Developer",
            description="We want a react developer"
        )
        client.delete()  # Actually delete the client from the database

        # Re-fetch the project from the database to get the updated state
        project.refresh_from_db()

        self.assertEqual(project.title, str(project))
        self.assertIsNone(project.client)  # Check if the client is set to None
        self.assertEqual(project.status, 'open')
    def test_create_contract(self):
        client = models.Client.objects.create_user(
            email='client@example.com',
            password='testpass123',
            company_name='Test Client Company'
        )
        freelancer = models.Freelancer.objects.create_user(
            email='freelancer@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        project = models.Project.objects.create(
            client=client,
            title='Project 1',
            description='A sample project',
            budget=1000,
            deadline='2024-07-31'
        )

        contract = models.Contract.objects.create(
            client = client,
            freelancer = freelancer,
            project= project,
            terms = 'These are the contract terms.',
            start_date= '2024-07-01T00:00:00Z',
            end_date= '2024-08-01T00:00:00Z',
            amount_agreed = '1000.00',
            payment_terms = 'Payment will be made in full upon completion.',
            freelancer_accepted_terms= False,
            status= 'active',
            payment_status= 'not_started'
        ) 
        self.assertEqual(str(contract) , f"Contract for {project.title} between {client.company_name} and {freelancer.first_name} {freelancer.last_name}")


    