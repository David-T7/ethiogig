from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from core.models import Freelancer
from rest_framework import status

class FreelancerSearchViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create some freelancers
        Freelancer.objects.create(
            email="freelancer1@example.com",
            full_name="Freelancer One",
            professional_title="Software Developer",
            skills=["Python", "Django", "REST"],
            experience=5,
            preferred_working_hours="full_time",
        )
        Freelancer.objects.create(
            email="freelancer2@example.com",
            full_name="Freelancer Two",
            professional_title="Data Scientist",
            skills=["Python", "Machine Learning", "Data Analysis"],
            experience=3,
            preferred_working_hours="part_time",
        )
        Freelancer.objects.create(
            email="freelancer3@example.com",
            full_name="Freelancer Three",
            professional_title="Web Developer",
            skills=["JavaScript", "React", "Node.js"],
            experience=4,
            preferred_working_hours="hourly",
        )

    def test_search_by_tech_stack(self):
        response = self.client.get(reverse('freelancer_search'), {'tech_stack': ['Python', 'Django']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['freelancers']), 2)
        self.assertEqual(response.data['freelancers'][0]['full_name'], "Freelancer One")

    def test_search_by_tech_stack_and_working_preference(self):
        response = self.client.get(reverse('freelancer_search'), {'tech_stack': ['Python'], 'working_preference': 'part_time'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print("both tech and working preference response is ",response.data)
        self.assertEqual(len(response.data['freelancers']), 1)
        self.assertEqual(response.data['freelancers'][0]['full_name'], "Freelancer Two")

    def test_search_no_results(self):
        response = self.client.get(reverse('freelancer_search'), {'tech_stack': ['GoLang']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print("no result response is ",response.data)
        self.assertEqual(len(response.data['freelancers']), 0)
