from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from core.models import Dispute, Contract, Client, Freelancer, Project ,SupportingDocument
from project.serializers import DisputeSerializer
from django.core.files.uploadedfile import SimpleUploadedFile
import os

DISPUTE_URL = reverse('project:dispute-list')

class PrivateDisputeApiTests(TestCase):
    """Test the private features of the dispute API"""

    def setUp(self):
        self.client_user = Client.objects.create_user(
            email='client@example.com',
            password='testpass123',
            company_name='Client Company'
        )
        self.freelancer_user = Freelancer.objects.create(
            email='freelancer@gmail.com',
            password='test123',
            first_name='Freelancer',
            last_name='User',
        )
        self.project = Project.objects.create(
            client=self.client_user,
            title='Project 1',
            description='We need a developer',
            budget=100.00,
            deadline='2024-07-31',
        )
        self.contract = Contract.objects.create(
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
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.client_user)
    
    def tearDown(self):
        """Clean up any files created during the test"""
        documents = SupportingDocument.objects.all()
        for document in documents:
            if os.path.exists(document.file.path):
                os.remove(document.file.path)

    def test_create_dispute_with_documents(self):
        """Test creating a dispute with supporting documents"""
        with open('test_documents/document.pdf', 'rb') as doc1:
            document1 = SimpleUploadedFile('document1.pdf', doc1.read(), content_type='application/pdf')
        with open('test_documents/document2.pdf', 'rb') as doc2:
            document2 = SimpleUploadedFile('document2.pdf', doc2.read(), content_type='application/pdf')

        payload = {
            'contract': self.contract.id,
            'title': 'Payment issue',
            'description': 'Freelancer did not receive payment',
            'return_type': 'partial',
            'return_amount': 50.00,
            'supporting_documents': [document1, document2]  # List of SimpleUploadedFile instances
        }
        res = self.client.post(DISPUTE_URL, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Dispute.objects.count(), 1)
        dispute = Dispute.objects.get(id=res.data['id'])
        self.assertEqual(dispute.title, payload['title'])
        self.assertEqual(dispute.description, payload['description'])
        self.assertEqual(dispute.return_type, payload['return_type'])
        self.assertEqual(float(dispute.return_amount), payload['return_amount'])  # Ensure decimal comparison
        self.assertTrue(dispute.supporting_documents.exists())  # Check if documents are attached
        self.assertEqual(dispute.supporting_documents.count(), 2)  # Check the number of documents attached
    
    def test_create_dispute_without_documents(self):
        """Test creating a dispute without supporting documents"""
        payload = {
            'contract': self.contract.id,
            'title': 'Payment issue',
            'description': 'Freelancer did not receive payment',
            'return_type': 'partial',
            'return_amount': 50.00,
        }
        res = self.client.post(DISPUTE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Dispute.objects.count(), 1)
        dispute = Dispute.objects.get(id=res.data['id'])
        self.assertEqual(dispute.title, payload['title'])
        self.assertEqual(dispute.description, payload['description'])
        self.assertEqual(dispute.return_type, payload['return_type'])
        self.assertEqual(float(dispute.return_amount), payload['return_amount'])
        self.assertFalse(dispute.supporting_documents.exists())  # Ensure no documents are attached
    
    def test_create_dispute_with_one_document(self):
        """Test creating a dispute with one supporting document"""
        with open('test_documents/document.pdf', 'rb') as doc1:
            document1 = SimpleUploadedFile('document1.pdf', doc1.read(), content_type='application/pdf')

        payload = {
            'contract': self.contract.id,
            'title': 'Payment issue',
            'description': 'Freelancer did not receive payment',
            'return_type': 'partial',
            'return_amount': 50.00,
            'supporting_documents': [document1]
        }
        res = self.client.post(DISPUTE_URL, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Dispute.objects.count(), 1)
        dispute = Dispute.objects.get(id=res.data['id'])
        self.assertEqual(dispute.title, payload['title'])
        self.assertEqual(dispute.description, payload['description'])
        self.assertEqual(dispute.return_type, payload['return_type'])
        self.assertEqual(float(dispute.return_amount), payload['return_amount'])
        self.assertTrue(dispute.supporting_documents.exists())  # Ensure documents are attached
        self.assertEqual(dispute.supporting_documents.count(), 1)  # Check the number of documents attached
    
    def test_add_documents_to_existing_dispute(self):
        """Test adding supporting documents to an existing dispute"""
        # Create a dispute with initial documents (if needed)
        dispute = Dispute.objects.create(
            contract=self.contract,
            title='Payment issue',
            freelancer=self.freelancer_user,
            client = self.client_user,
            description='Freelancer did not receive payment',
            return_type='partial',
            return_amount=50.00,
        )
        # Attach initial documents (if needed)
        initial_document = SupportingDocument.objects.create(
            dispute=dispute,
            file=SimpleUploadedFile('initial_document.pdf', b'Test content', content_type='application/pdf'),
            uploaded_by=self.client_user
        )

        initial_document_count = dispute.supporting_documents.count()

        # Upload additional documents
        with open('test_documents/document.pdf', 'rb') as doc1:
            document1 = SimpleUploadedFile('document1.pdf', doc1.read(), content_type='application/pdf')
        with open('test_documents/document2.pdf', 'rb') as doc2:
            document2 = SimpleUploadedFile('document2.pdf', doc2.read(), content_type='application/pdf')

        payload = {
            'supporting_documents': [document1, document2]
        }
        url = reverse('project:dispute-detail', kwargs={'pk': dispute.id})
        res = self.client.patch(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dispute.refresh_from_db()
        self.assertEqual(dispute.supporting_documents.count(), initial_document_count + 2)  # Check the updated count
    def test_remove_documents_from_dispute(self):
        """Test removing supporting documents from a dispute"""
        # Assume self.dispute already has some documents attached (setUp method)
        
        # initial_document_count = self.dispute.supporting_documents.count()
        dispute = Dispute.objects.create(
            contract=self.contract,
            title='Payment issue',
            freelancer=self.freelancer_user,
            client = self.client_user,
            description='Freelancer did not receive payment',
            return_type='partial',
            return_amount=50.00,
        )
        payload = {
            'supporting_documents': []  # Empty list to remove all documents
        }
        url = reverse('project:dispute-detail', kwargs={'pk': dispute.id})
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dispute.refresh_from_db()
        self.assertEqual(dispute.supporting_documents.count(), 0)
    def test_update_documents_in_dispute(self):
        """Test updating supporting documents in a dispute"""
        # Assume self.dispute already has some documents attached (setUp method)
        dispute = Dispute.objects.create(
            contract=self.contract,
            title='Payment issue',
            freelancer=self.freelancer_user,
            client = self.client_user,
            description='Freelancer did not receive payment',
            return_type='partial',
            return_amount=50.00,
        )
        initial_document_count = dispute.supporting_documents.count()

        # Upload a new document to replace an existing one
        with open('test_documents/document.pdf', 'rb') as new_doc:
            new_document = SimpleUploadedFile('new_document.pdf', new_doc.read(), content_type='application/pdf')

        payload = {
            'supporting_documents': [
                new_document,
                # You can also include existing documents if you want to update them
                # SimpleUploadedFile('existing_document.pdf', existing_doc.read(), content_type='application/pdf'),
            ]
        }
        url = reverse('project:dispute-detail', kwargs={'pk': dispute.id})
        res = self.client.patch(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dispute.refresh_from_db()
        self.assertEqual(dispute.supporting_documents.count(), initial_document_count + 1)  # Check the updated count