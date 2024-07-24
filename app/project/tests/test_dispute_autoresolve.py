from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from project.tasks import check_unresolved_disputes
from core.models import Dispute, Client, Freelancer, Contract
DISPUTE_URL = reverse('project:dispute-list')

class DisputeApiTests(TestCase):
    def setUp(self):
        self.client_user = Client.objects.create_user(email='client@example.com', password='password123')
        self.freelancer_user = Freelancer.objects.create_user(email='freelancer@example.com', password='password123' , first_name='test',last_name='test last')
        self.contract = Contract.objects.create(client=self.client_user, freelancer=self.freelancer_user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.client_user)

    def test_create_dispute(self):
        """Test creating a dispute"""
        payload = {
            'title': 'Payment issue',
            'description': 'Freelancer did not receive payment',
            'return_type': 'partial',
            'freelancer':self.freelancer_user.id,
            'client':self.client_user.id,
            'return_amount': 50.00,
            'contract': self.contract.id
        }
        res = self.client.post(DISPUTE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], payload['title'])

    def test_auto_resolve_dispute(self):
        """Test that a dispute is auto-resolved if not responded to in time"""
        dispute = Dispute.objects.create(
            title='Payment issue',
            description='Freelancer did not receive payment',
            return_type='partial',
            return_amount=50.00,
            client=self.client_user,
            freelancer=self.freelancer_user,
            contract=self.contract,
            response_deadline=timezone.now() - timedelta(days=1)
        )

        # Run the Celery task
        check_unresolved_disputes()

        dispute.refresh_from_db()
        self.assertTrue(dispute.auto_resolved)
        self.assertEqual(dispute.status, 'auto_resolved')
