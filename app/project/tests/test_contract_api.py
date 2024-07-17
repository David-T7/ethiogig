from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from core import models
from ..serializers import ContractSerializer, ContractFreelancerSerializer

CONTRACT_URL = reverse('project:contract-list')
CONTRACT_DETAIL_URL = lambda pk: reverse('project:contract-detail', kwargs={'pk': pk})
FREELANCER_CONTRACT_DETAIL_URL = lambda pk: reverse('project:freelancer-contract-detail', kwargs={'pk': pk})

class PrivateContractApiTests(TestCase):
    """Test the private features of the Contract API"""

    def setUp(self):
        self.client_user = models.Client.objects.create(
            email='client@gmail.com',
            password='test123',
            company_name='Client Company',
        )
        self.freelancer_user = models.Freelancer.objects.create(
            email='freelancer@gmail.com',
            password='test123',
            first_name='Freelancer',
            last_name='User',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.client_user)

    def create_contract(self, project, freelancer):
        """Helper method to create a contract"""
        return models.Contract.objects.create(
            client=self.client_user,
            freelancer=freelancer,
            project=project,
            terms='Contract terms',
            start_date='2024-07-01',
            end_date='2024-08-01',
            amount_agreed=100.00,
            payment_terms='Payment terms',
            freelancer_accepted_terms=False,
            status='pending',
            payment_status='not_started',
        )

    def test_retrieve_contracts(self):
        """Test retrieving a list of contracts"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user)
        
        res = self.client.get(CONTRACT_URL)
        contracts = models.Contract.objects.filter(client=self.client_user)
        serializer = ContractSerializer(contracts, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_partial_update_contract(self):
        """Test partially updating a contract"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user)
        payload = {
            'terms': 'Updated contract terms'
        }
        res = self.client.patch(CONTRACT_DETAIL_URL(contract.pk), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['terms'], 'Updated contract terms')

    def test_full_update_contract(self):
        """Test fully updating a contract"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user)
        payload = {
            'terms': 'Updated contract terms',
            'start_date': '2024-07-01',
            'end_date': '2024-08-01',
            'amount_agreed': 150.00,
            'payment_terms': 'Updated payment terms',
            'status': 'active',
            'payment_status': 'in_progress'
        }
        res = self.client.put(CONTRACT_DETAIL_URL(contract.pk), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['amount_agreed'], '150.00')

    def test_delete_contract(self):
        """Test deleting a contract"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user)
        res = self.client.delete(CONTRACT_DETAIL_URL(contract.pk))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Contract.objects.filter(id=contract.pk).exists())

    def test_permission_denied_freelancer_accepted_terms(self):
        """Test that client cannot update freelancer_accepted_terms"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user)
        payload = {
            'freelancer_accepted_terms': True
        }
        res = self.client.patch(CONTRACT_DETAIL_URL(contract.pk), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class PrivateFreelancerContractApiTests(TestCase):
    """Test the private features of the Freelancer Contract API"""

    def setUp(self):
        self.client_user = models.Client.objects.create(
            email='client@gmail.com',
            password='test123',
            company_name='Client Company',
        )
        self.freelancer_user = models.Freelancer.objects.create(
            email='freelancer@gmail.com',
            password='test123',
            first_name='Freelancer',
            last_name='User',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.freelancer_user)

    def create_contract(self, project):
        """Helper method to create a contract"""
        return models.Contract.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            project=project,
            terms='Contract terms',
            start_date='2024-07-01',
            end_date='2024-08-01',
            amount_agreed=100.00,
            payment_terms='Payment terms',
            freelancer_accepted_terms=False,
            status='pending',
            payment_status='not_started',
        )

    def test_partial_update_freelancer_accepted_terms(self):
        """Test partially updating freelancer_accepted_terms"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project)
        payload = {
            'freelancer_accepted_terms': True
        }
        res = self.client.patch(FREELANCER_CONTRACT_DETAIL_URL(contract.pk), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['freelancer_accepted_terms'], True)

    def test_permission_denied_for_full_update(self):
        """Test that freelancer cannot perform full update"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project)
        payload = {
            'terms': 'Updated contract terms',
            'start_date': '2024-07-01',
            'end_date': '2024-08-01',
            'amount_agreed': 150.00,
            'payment_terms': 'Updated payment terms',
            'freelancer_accepted_terms': True,
            'status': 'active',
            'payment_status': 'in_progress'
        }
        res = self.client.put(FREELANCER_CONTRACT_DETAIL_URL(contract.pk), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)