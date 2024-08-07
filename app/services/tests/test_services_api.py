# tests.py

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Service, Technology

class ServiceTests(APITestCase):
    def setUp(self):
        self.technology = Technology.objects.create(name="Django", description="A high-level Python web framework")
        self.service_data = {
            "name": "Web Development",
            "description": "Professional web development services.",
            "price": "1500.00",
            "technology_ids": [self.technology.id]
        }

    def test_create_service(self):
        url = reverse('service-list')
        response = self.client.post(url, self.service_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Service.objects.count(), 1)
        self.assertEqual(Service.objects.get().name, 'Web Development')
        self.assertEqual(Service.objects.get().technologies.count(), 1)

    def test_get_services(self):
        service = Service.objects.create(
            name="Web Development",
            description="Professional web development services.",
            price="1500.00"
        )
        service.technologies.add(self.technology)
        url = reverse('service-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Web Development')
        self.assertEqual(len(response.data[0]['technologies']), 1)
        self.assertEqual(response.data[0]['technologies'][0]['name'], 'Django')

    def test_update_service(self):
        service = Service.objects.create(
            name="Web Development",
            description="Professional web development services.",
            price="1500.00"
        )
        service.technologies.add(self.technology)
        url = reverse('service-detail', args=[service.id])
        updated_data = {
            "name": "Updated Web Development",
            "description": "Updated description.",
            "price": "1800.00",
            "technology_ids": [self.technology.id]
        }
        response = self.client.put(url, updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        service.refresh_from_db()
        self.assertEqual(service.name, 'Updated Web Development')
        self.assertEqual(service.technologies.count(), 1)

    def test_delete_service(self):
        service = Service.objects.create(
            name="Web Development",
            description="Professional web development services.",
            price="1500.00"
        )
        service.technologies.add(self.technology)
        url = reverse('service-detail', args=[service.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Service.objects.count(), 0)

class TechnologyTests(APITestCase):
    def test_create_technology(self):
        url = reverse('technology-list')
        data = {
            "name": "React",
            "description": "A JavaScript library for building user interfaces"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Technology.objects.count(), 1)
        self.assertEqual(Technology.objects.get().name, 'React')

    def test_get_technologies(self):
        Technology.objects.create(name="React", description="A JavaScript library for building user interfaces")
        url = reverse('technology-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'React')
