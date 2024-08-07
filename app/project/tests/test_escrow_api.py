from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from core import models
from ..serializers import EscrowSerializer
ESCROW_URL = reverse('project:escrow-list',)

ESCROW_DETAIL_URL = lambda pk:reverse('project:escrow-detail',kwargs={'pk': pk})
ESCROW_MILESTONE_URL = lambda milestone_id: reverse('project:milestone-escrows-list', kwargs={'milestone_pk':milestone_id})
ESCROW_CONTRACT_URL = lambda contract_id: reverse('project:contract-escrows-list',kwargs={'contract_pk':contract_id})
DEPOSIT_CONFIRM_URL = lambda pk:reverse('project:update-deposit-confirmed',kwargs={'pk': pk})
class PrivateEscrowApiTests(TestCase):
    """Test the private features of the Escrow API"""

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

    def create_contract(self, milestone_based=False):
        """Helper method to create a contract"""
        return models.Contract.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            project=models.Project.objects.create(
                client=self.client_user,
                title='Project 1',
                description='We need a developer',
                budget=100.00,
                deadline='2024-07-31',
            ),
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

    def create_escrow(self, contract, amount_deposited ,milestone=None):
        """Helper method to create an escrow record"""
        return models.Escrow.objects.create(
            contract=contract,
            milestone=milestone,  # You can add a milestone if needed
            amount=amount_deposited,
            status='Pending',
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

    def test_create_escrow(self):
        """Test creating an escrow record"""
        contract = self.create_contract()
        payload = {
            'contract': contract.pk,
            'status': 'Pending',
            'amount':100.00
        }
        res = self.client.post(ESCROW_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        escrow = models.Escrow.objects.get(id=res.data['id'])
        self.assertTrue(escrow.amount , contract.amount_agreed)
        self.assertEqual(escrow.status, 'Pending')

    def test_retrieve_escrows(self):
        """Test retrieving a list of escrow records"""
        contract = self.create_contract()
        self.create_escrow(contract, 100.00)
        res = self.client.get(ESCROW_URL)
        escrows = models.Escrow.objects.filter(contract=contract)
        serializer = EscrowSerializer(escrows, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_update_escrow(self):
        """Test updating an escrow record"""
        contract = self.create_contract()
        escrow = self.create_escrow(contract, 100.00)
        payload = {
            'status': 'Released'
        }
        res = self.client.patch(reverse('project:escrow-detail',kwargs={'pk': escrow.pk}) , payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        escrow.refresh_from_db()
        self.assertFalse(escrow.deposit_confirmed)
        self.assertEqual(escrow.status, 'Released')

    def test_delete_escrow(self):
        """Test deleting an escrow record"""
        contract = self.create_contract()
        escrow = self.create_escrow(contract, 100.00)
        url = reverse('project:escrow-detail',kwargs={'pk': escrow.pk})
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Escrow.objects.filter(id=escrow.pk).exists())

    def test_check_escrow_fulfillment(self):
        """Test checking if escrow amount matches agreed amount for full payment"""
        contract = self.create_contract()
        models.Escrow.objects.create(
            contract=contract,
            status='Released',
            amount = 100.00
        )
        contract.status ='completed'

        # Assuming you have a method to check if escrow is fulfilled
        self.assertTrue(contract.is_escrow_fulfilled())

    def test_check_partial_escrow_fulfillment(self):
        """Test partial fulfillment of escrow for milestone-based contracts"""
        contract = self.create_contract(milestone_based=True)
        milestone = self.create_milestone(contract)
        models.Escrow.objects.create(
            contract=contract,
            milestone=milestone,
            status='Released',
            amount = milestone.amount
        )
        # Assuming you have a method to check if escrow is fulfilled
        self.assertTrue(contract.is_escrow_fulfilled())

    def test_create_escrow_with_milestone(self):
        """Test creating an escrow record with a milestone"""
        contract = self.create_contract(milestone_based=True)
        milestone = self.create_milestone(contract)
        payload = {
            'contract': contract.pk,
            'milestone': milestone.pk,
            'amount':milestone.amount,
            'status': 'Pending'
        }
        res = self.client.post(ESCROW_MILESTONE_URL(milestone.pk), payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        escrow = models.Escrow.objects.get(id=res.data['id'])
        self.assertEqual(escrow.deposit_confirmed, False)
        self.assertEqual(escrow.status, 'Pending')
        self.assertEqual(escrow.milestone.pk, milestone.pk)

    def test_reterive_escrow_with_milestone(self):
        """Test reteriving an escrow record with a milestone"""
        contract = self.create_contract(milestone_based=True)
        milestone = self.create_milestone(contract)
        escrow = self.create_escrow(contract, amount_deposited=True , milestone=milestone)
        url = ESCROW_MILESTONE_URL(milestone.pk)
        res = self.client.get(url)
        print("escrow milestone result",res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # serializer = EscrowSerializer(escrow)
        # print("escrow milestone serializer result",serializer.data)
        self.assertEqual(res.data[0]['id'], str(escrow.pk))

    def test_reterive_escrow_with_contract(self):
        """Test retrieving an escrow record with a contract"""
        contract = self.create_contract(milestone_based=True)
        milestone = self.create_milestone(contract)
        self.create_escrow(contract, milestone.amount , milestone)
        res = self.client.get(ESCROW_CONTRACT_URL(contract.pk))
        escrows = models.Escrow.objects.filter(contract=contract)
        serializer = EscrowSerializer(escrows, many=True)
        # print("serializer data is ",serializer.data)
        # print("res data is ",res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_deposit_confirmation_with_milestone(self):
        """Test deleting an escrow record with a milestone"""
        admin = models.User.objects.create_superuser(
            email='admin2@gmail.com',
            password='admin2',
        )
        contract = self.create_contract(milestone_based=True)
        milestone = self.create_milestone(contract)
        escrow = self.create_escrow(contract, milestone.amount , milestone)
        self.client.force_authenticate(user=admin)
        url = DEPOSIT_CONFIRM_URL(escrow.pk)
        payload ={
            'deposit_confirmed':True
        }
        res = self.client.patch(url , payload , format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        escrow.refresh_from_db()
        self.assertTrue(escrow.deposit_confirmed)

class PublicEscrowApiTests(TestCase):
    """Test the public features of the Escrow API"""

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

    def test_create_escrow_unauthorized(self):
        """Test that unauthorized users cannot create escrow records"""
        payload = {
            'contract': self.contract.pk,
            'status': 'Pending',
            'amount':50.00
        }
        res = self.client.post(ESCROW_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_escrows(self):
        """Test retrieving escrow records with public access"""
        res = self.client.get(ESCROW_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_escrow_detail(self):
        """Test retrieving escrow details with public access"""
        escrow = models.Escrow.objects.create(
            contract=self.contract,
            status='Pending',
            amount = 50.00  
        )
        res = self.client.get(ESCROW_DETAIL_URL(escrow.pk))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

