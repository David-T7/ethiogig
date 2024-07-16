from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from core import models
from ..serializers import ProjectSerializer

PROJECT_URL = reverse('project:project-list')
PROJECT_UPDATE_URL = reverse('project:project-detail', kwargs={'pk': 1})  # Replace '1' with an actual project ID


class PrivateApiTests(TestCase):
    """Test the private features of the API"""

    def setUp(self):
        self.user = models.Client.objects.create(
            email='test@gmail.com',
            password='test123',
            company_name='Test Company',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def create_project(self, title):
        """Helper method to create a project"""
        return models.Project.objects.create(
            client=self.user,
            title=title,
            description='We need a react developer',
            budget=23.3,
            deadline='2024-07-31',
        )

    def test_retrieve_projects(self):
        """Test retrieving a list of projects"""
        self.create_project("project 1")
        self.create_project("project 2")

        res = self.client.get(PROJECT_URL)
        projects = models.Project.objects.filter(client=self.user)
        serializer = ProjectSerializer(projects, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_partial_update_project(self):
        """Test partially updating a project"""
        project = self.create_project("project 1")
        payload = {
            'title': 'project 2'
        }
        res = self.client.patch(reverse('project:project-detail', kwargs={'pk': project.pk}), payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], 'project 2')

    def test_full_update_project(self):
        """Test fully updating a project"""
        project = self.create_project("project 1")
        payload = {
            'title': 'project 2',
            'client': self.user.pk,
            'description': 'We need a react developer',
            'budget': 23.3,
            'deadline': '2024-07-31',
            'status': 'open'
        }
        res = self.client.put(reverse('project:project-detail', kwargs={'pk': project.pk}), payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], 'project 2')
