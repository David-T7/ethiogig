from unittest.mock import patch
from django.test import TestCase 
from django.contrib.auth import get_user_model
from core import models
import uuid
import tempfile
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
            full_name = "Dawit Tesfaye",
        )
        self.assertEqual(freelancer.full_name, str(freelancer))
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
            full_name = "Dawit Tesfaye",
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
        self.assertEqual(str(contract) , f"Contract for {project.title} between {client.company_name} and {freelancer.full_name}")






class ResumeModelTest(TestCase):

    def setUp(self):
        self.resume_data = {
            "full_name": "John Doe",
            "email": "john.doe@example.com",
            'password':"testpass",
            "position_applied_for": "Software Engineer"
        }
        self.resume_file = tempfile.NamedTemporaryFile(suffix=".pdf")
        self.resume_file.write(b"Sample resume content")
        self.resume_file.seek(0)
        self.resume = models.Resume.objects.create(
            full_name=self.resume_data['full_name'],
            email=self.resume_data['email'],
            position_applied_for=self.resume_data['position_applied_for'],
            resume_file=self.resume_file.name
        )

    def test_resume_creation(self):
        self.assertEqual(self.resume.full_name, "John Doe")
        self.assertEqual(self.resume.email, "john.doe@example.com")
        self.assertEqual(self.resume.position_applied_for, "Software Engineer")
        self.assertTrue(self.resume.resume_file)

    def test_resume_str(self):
        self.assertEqual(str(self.resume), "John Doe")

class ScreeningResultModelTest(TestCase):

    def setUp(self):
        self.resume = models.Resume.objects.create(
            full_name="John Doe",
            email="john.doe@example.com",
            password="testpass",
            position_applied_for="Software Engineer",
            resume_file=tempfile.NamedTemporaryFile(suffix=".pdf").name
        )
        self.screening_result = models.ScreeningResult.objects.create(
            resume=self.resume,
            score=85.5,
            passed=True,
            comments="Great resume!"
        )

    def test_screening_result_creation(self):
        self.assertEqual(self.screening_result.resume, self.resume)
        self.assertEqual(self.screening_result.score, 85.5)
        self.assertTrue(self.screening_result.passed)
        self.assertEqual(self.screening_result.comments, "Great resume!")

    def test_screening_result_str(self):
        expected_str = f"resume screening result for {self.resume.full_name} score :{self.screening_result.score} passed:{self.screening_result.passed}"
        self.assertEqual(str(self.screening_result), expected_str)

class ScreeningConfigModelTest(TestCase):

    def setUp(self):
        self.screening_config = models.ScreeningConfig.objects.create(passing_score_threshold=75.0)

    def test_screening_config_creation(self):
        self.assertEqual(self.screening_config.passing_score_threshold, 75.0)

    def test_screening_config_str(self):
        self.assertEqual(str(self.screening_config), "Passing Score Threshold: 75.0")



class TechnologyModelTests(TestCase):
    def setUp(self):
        self.tech = models.Technology.objects.create(
            name="Django",
            description="A high-level Python web framework"
        )

    def test_technology_creation(self):
        self.assertEqual(self.tech.name, "Django")
        self.assertEqual(self.tech.description, "A high-level Python web framework")
        self.assertIsInstance(self.tech.id, uuid.UUID)
        self.assertEqual(str(self.tech), "Django")

class ServiceModelTests(TestCase):
    def setUp(self):
        self.tech = models.Technology.objects.create(
            name="Django",
            description="A high-level Python web framework"
        )
        self.service = models.Services.objects.create(
            name="Web Development",
            description="Professional web development services.",
        )
        self.service.technologies.add(self.tech)

    def test_service_creation(self):
        self.assertEqual(self.service.name, "Web Development")
        self.assertEqual(self.service.description, "Professional web development services.")
        self.assertIsInstance(self.service.id, uuid.UUID)
        self.assertEqual(str(self.service), "Web Development")
        self.assertIn(self.tech, self.service.technologies.all())

    def test_service_update(self):
        self.service.name = "Updated Web Development"
        self.service.save()
        self.service.refresh_from_db()
        self.assertEqual(self.service.name, "Updated Web Development")

    def test_service_delete(self):
        service_id = self.service.id
        self.service.delete()
        self.assertFalse(models.Services.objects.filter(id=service_id).exists())
