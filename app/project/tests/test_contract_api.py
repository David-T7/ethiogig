from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from core import models
from ..serializers import ContractSerializer, ContractFreelancerSerializer, MilestoneSerializer

CONTRACT_URL = reverse('project:contract-list')
CONTRACT_DETAIL_URL = lambda pk: reverse('project:contract-detail', kwargs={'pk': pk})
FREELANCER_CONTRACT_DETAIL_URL = lambda pk: reverse('project:freelancer-contract-detail', kwargs={'pk': pk})
MILESTONE_URL = lambda contract_pk: reverse('project:contract-milestones-list', kwargs={'contract_pk': contract_pk})
MILESTONE_DETAIL_URL = lambda contract_pk, pk: reverse('project:contract-milestones-detail', kwargs={'contract_pk': contract_pk, 'pk': pk})

class PrivateContractApiTests(TestCase):
    """Test the private features of the Contract API"""

    def setUp(self):
        self.client_user = models.Client.objects.create_user(
            email='client@gmail.com',
            password='test123',
            company_name='Client Company',
        )
        self.freelancer_user = models.Freelancer.objects.create_user(
            email='freelancer@gmail.com',
            password='test123',
            full_name='Freelancer',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.client_user)

    def create_contract(self, project, freelancer, milestone_based=False):
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
            milestone_based=milestone_based
        )

    def create_milestone(self, contract):
        """Helper method to create a milestone"""
        return models.Milestone.objects.create(
            contract=contract,
            title='Milestone 1',
            description='Complete part 1',
            amount=50.00,
            due_date='2024-07-15'
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

    def test_create_milestone(self):
        """Test creating a milestone"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user, milestone_based=True)
        payload = {
            'contract': contract.pk,
            'title': 'Milestone 1',
            'description': 'Complete part 1',
            'amount': 50.00,
            'due_date': '2024-07-15T00:00:00Z'  # Ensure proper format
        }
        res = self.client.post(MILESTONE_URL(contract.pk), payload, format='json')
        print("test create milestone result is ", res.data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        milestone = models.Milestone.objects.get(id=res.data['id'])

        # Check each field in payload
        for key in payload.keys():
            if key == 'contract':
                # Compare contract IDs
                self.assertEqual(payload[key], milestone.contract.pk)
            elif isinstance(payload[key], str) and 'date' in key:
                # Compare date fields
                self.assertEqual(payload[key], milestone.__dict__[key].strftime('%Y-%m-%dT%H:%M:%SZ'))
            else:
                # Compare other fields
                self.assertEqual(payload[key], getattr(milestone, key))

    def test_update_milestone(self):
        """Test updating a milestone"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user, milestone_based=True)
        milestone = models.Milestone.objects.create(
            contract=contract,
            title='Milestone 1',
            description='Complete part 1',
            amount=50.00,
            due_date='2024-07-15T00:00:00Z'  # Ensure proper format
        )
        payload = {
            'title': 'Updated Milestone',
            'description': 'Complete part 1 - updated',
            'amount': 75.00,
            'due_date': '2024-07-20T00:00:00Z'  # Ensure proper format
        }
        url = MILESTONE_DETAIL_URL(contract.pk, milestone.pk)  # Corrected URL formation
        res = self.client.patch(url, payload, format='json')
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        milestone.refresh_from_db()
        self.assertEqual(milestone.title, 'Updated Milestone')
        self.assertEqual(milestone.amount, 75.00)
        self.assertEqual(milestone.due_date.strftime('%Y-%m-%dT%H:%M:%SZ'), '2024-07-20T00:00:00Z')

    def test_retrieve_milestones(self):
        """Test retrieving milestones for a contract"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user, milestone_based=True)
        milestone = self.create_milestone(contract)

        res = self.client.get(MILESTONE_URL(contract.pk))
        milestones = models.Milestone.objects.filter(contract=contract)
        serializer = MilestoneSerializer(milestones, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_delete_milestone(self):
        """Test deleting a milestone"""
        project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        contract = self.create_contract(project, self.freelancer_user, milestone_based=True)
        milestone = self.create_milestone(contract)
        url = MILESTONE_DETAIL_URL(contract.pk, milestone.pk)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Milestone.objects.filter(id=milestone.pk).exists())

class PublicContractApiTests(TestCase):
    """Test the public features of the Contract API"""

    def setUp(self):
        self.client = APIClient()
        self.client_user = models.Client.objects.create_user(
            email='client@gmail.com',
            password='test123',
            company_name='Client Company',
        )
        self.freelancer_user = models.Freelancer.objects.create_user(
            email='freelancer@gmail.com',
            password='test123',
            full_name='Freelancer',
        )
        self.project = models.Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        self.contract = models.Contract.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            project=self.project,
            terms='Contract terms',
            start_date='2024-07-01',
            end_date='2024-08-01',
            amount_agreed=100.00,
            payment_terms='Payment terms',
            freelancer_accepted_terms=False,
            status='pending',
            payment_status='not_started',
            milestone_based=False
        )

    def test_create_contract_unauthorized(self):
        """Test that unauthorized users cannot create contracts"""
        payload = {
            'client': self.client_user.pk,
            'freelancer': self.freelancer_user.pk,
            'project': self.project.pk,
            'terms': 'Contract terms',
            'start_date': '2024-07-01',
            'end_date': '2024-08-01',
            'amount_agreed': 100.00,
            'payment_terms': 'Payment terms',
            'freelancer_accepted_terms': False,
            'status': 'pending',
            'payment_status': 'not_started',
        }
        res = self.client.post(CONTRACT_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_contracts(self):
        """Test retrieving contracts with public access"""
        res = self.client.get(CONTRACT_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_contract_detail(self):
        """Test retrieving contract details with public access"""
        res = self.client.get(CONTRACT_DETAIL_URL(self.contract.pk))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
