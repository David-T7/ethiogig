# tests.py

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Services, Technology

class ServiceTests(APITestCase):
    def setUp(self):
        self.technology = Technology.objects.create(name="Django", description="A high-level Python web framework")
        self.service_data = {
            "name": "Web Development",
            "description": "Professional web development services.",
            "technology_ids": [self.technology.id]
        }


    def test_get_services(self):
        service = Services.objects.create(
            name="Web Development",
            description="Professional web development services.",
        )
        service.technologies.add(self.technology)
        url = reverse('services-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Web Development')
        self.assertEqual(len(response.data[0]['technologies']), 1)
        self.assertEqual(response.data[0]['technologies'][0]['name'], 'Django')


class TechnologyTests(APITestCase):

    def test_get_technologies(self):
        Technology.objects.create(name="React", description="A JavaScript library for building user interfaces")
        url = reverse('technology-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'React')
