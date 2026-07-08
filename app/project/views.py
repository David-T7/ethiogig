import logging
from decimal import Decimal, InvalidOperation

from rest_framework import viewsets, generics, status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed, ValidationError
from project import serializers
from core import models
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Count, Q, F
from datetime import timedelta
from .utils import send_email

logger = logging.getLogger(__name__)

CONTRACT_STATUS_TRANSITIONS = {
    'draft':           {'pending', 'canceled'},
    'pending':         {'draft', 'canceled'},
    'accepted':        {'active', 'canceled'},
    'active':          {'completed', 'inDispute'},
    'pendingApproval': {'completed', 'active'},
    'completed':       set(),
    'canceled':        set(),
    'inDispute':       set(),
}


class ProjectViewSet(viewsets.ModelViewSet):
    """View for managing projects of a client"""
    serializer_class = serializers.ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models.Project.objects.filter(client=self.request.user.client)

    def perform_create(self, serializer):
        client = self.request.user.client
        if models.Project.objects.filter(client=client, title=serializer.validated_data['title']).exists():
            raise ValidationError({"title": "Title already used."})
        serializer.save(client=client)

    def perform_update(self, serializer):
        instance = self.get_object()
        client = self.request.user.client
        if models.Project.objects.filter(
            client=client, title=serializer.validated_data['title']
        ).exclude(id=instance.id).exists():
            raise ValidationError({"title": "Title already used by another project."})
        serializer.save()

    def perform_destroy(self, instance):
        """Delete a project"""
        # Check if the project is associated with any contract with a status other than "draft"
        if models.Contract.objects.filter(project=instance).exclude(status="draft").exists():
            raise ValidationError({"project": "This project is associated with a contract that is not in draft status and cannot be deleted."})

        # If no associated contract is found with a status other than "draft", delete the project
        instance.delete()

class FreelancerProjectViewSet(viewsets.ModelViewSet):
    """View for managing projects a freelancer is involved in"""
    serializer_class = serializers.ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return projects where the freelancer is involved"""
        # Get the freelancer associated with the authenticated user
        freelancer = self.request.user.freelancer

        # Get contracts associated with the freelancer
        contracts = models.Contract.objects.filter(freelancer=freelancer)

        # Get project IDs from these contracts
        project_ids = contracts.values_list('project_id', flat=True)

        # Filter projects by these IDs
        return models.Project.objects.filter(id__in=project_ids)

    def list(self, request, *args, **kwargs):
        """List projects a freelancer is involved in"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single project a freelancer is involved in"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

class MilestoneListViewSet(generics.ListAPIView):
    """View for managing milestones"""
    queryset = models.Milestone.objects.all()
    serializer_class = serializers.MilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        contract_id = self.kwargs.get('contract_id')
        return models.Milestone.objects.filter(contract_id=contract_id)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CounterOfferMilestoneListViewSet(generics.ListAPIView):
    """View for managing milestones related to a specific counter offer."""
    serializer_class = serializers.CounterOfferMilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        counter_offer_id = self.kwargs.get('counter_offer_id')
        return models.CounterOfferMilestone.objects.filter(counter_offer_id=counter_offer_id)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ContractViewSet(viewsets.ModelViewSet):
    """Viewset for managing contracts between client and freelancer"""
    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Set the client automatically based on the logged-in user."""
        serializer.save(client=self.request.user.client)

    def get_queryset(self):
        """Limit queryset to contracts involving the current client."""
        return self.queryset.filter(client=self.request.user.client)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if 'freelancer_accepted_terms' in request.data:
            raise PermissionDenied("You do not have permission to update freelancer_accepted_terms.")
        if request.user.client != instance.client:
            raise PermissionDenied("You do not have permission to update this contract.")

        new_status = request.data.get('status')
        if new_status and new_status != instance.status:
            allowed = CONTRACT_STATUS_TRANSITIONS.get(instance.status, set())
            if new_status not in allowed:
                return Response(
                    {'error': f"Cannot transition contract from '{instance.status}' to '{new_status}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Auto-release escrow when a non-milestone contract is marked completed
        new_status = request.data.get('status')
        if new_status == 'completed' and not instance.milestone_based:
            escrow = models.Escrow.objects.filter(contract=instance, milestone__isnull=True).first()
            if escrow:
                escrow.release()

        message = ""
        subject = ""
        if 'status' in request.data and request.data['status'] == 'pending':
            message = "You have received a contract offer."
            subject = "Contract Offer"
        else:
            message = f"Contract status updated to " + request.data['status']
            subject = "Contract status updated"
        html_content = f"""
        <html>
        <body>
            <p>{message}</p>
        </body>
        </html>
        """
        send_email(instance.freelancer.email, subject, html_content)
        models.Notification.objects.create(
                    user=instance.client,
                    type='alert',
                    title=f"Contract status updated",
                    description=f"Contract {instance.title} status updated to {instance.status}"
            )
        models.Notification.objects.create(
                    user=instance.freelancer,
                    type='alert',
                    title=subject,
                    description=message
            )
        return Response(serializer.data)


class ContractListView(generics.RetrieveAPIView):
    """View for getting a single contract — scoped to the authenticated user's own contracts."""
    serializer_class = serializers.ContractSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_client = getattr(user, 'client', None)
        user_freelancer = getattr(user, 'freelancer', None)
        qs = models.Contract.objects.none()
        if user_client:
            qs = qs | models.Contract.objects.filter(client=user_client)
        if user_freelancer:
            qs = qs | models.Contract.objects.filter(freelancer=user_freelancer)
        return qs


class FreelancerContractViewSet(generics.RetrieveUpdateAPIView):
    """Viewset for updating terms acceptance by freelancer"""
    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractFreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset to only include contracts belonging to the authenticated freelancer"""
        return self.queryset.filter(freelancer=self.request.user.freelancer)

    def get_object(self):
        """Retrieve and return the contract by ID belonging to the authenticated freelancer"""
        queryset = self.get_queryset()
        obj = generics.get_object_or_404(queryset, pk=self.kwargs.get('pk'))
        self.check_object_permissions(self.request, obj)
        return obj

    def put(self, request, *args, **kwargs):
        """Block PUT method to prevent full updates"""
        raise MethodNotAllowed("PUT method not allowed. Please use PATCH for partial updates.")

    def patch(self, request, *args, **kwargs):
        """Handle partial updates and update related milestones if they are pending"""
        contract = self.get_object()
        # Retrieve and handle the status field from the request
        status_to_update = request.data.get('status')
        if status_to_update:
            contract.status = status_to_update
            contract.save()
        else:
            contract.status = "accepted"
            contract.save()
        serializer = self.get_serializer(contract, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Update related milestones' status to 'accepted' if currently 'pending'
         # Update related milestones if the status is 'accepted'
        if status_to_update == 'accepted':
            milestones = models.Milestone.objects.filter(contract=contract, status='pending')
            for milestone in milestones:
                milestone.status = 'accepted'
                milestone.save()
        # else:
        #     contract_updated = contract.contract_update
        #     contract_updated.amount_agreed = contract.amount_agreed  
        #     contract_updated.terms = contract.terms  
        #     contract_updated.save()
        #     contract.delete()
        #     # Update related milestones' status to 'accepted' if currently 'pending'
        #     milestones = models.Milestone.objects.filter(contract=contract_updated, status='pending')
        #     for milestone in milestones:
        #         milestone.status = 'accepted'
        #         milestone.save()
        message = f"contract status for {contract.title} has been changed to {status_to_update}."
        html_content = f"""
        <html>
        <body>
            <p>{message}</p>
        </body>
        </html>
        """
        send_email(contract.client.email, "Contract status updated.", html_content)
        models.Notification.objects.create(
                user=contract.client,
                type='alert',
                title=f"Contract status updated",
                description=message
        )
        models.Notification.objects.create(
                user=contract.freelancer,
                type='alert',
                title=f"Contract status updated",
                description=message
        )
        return Response(status=status.HTTP_200_OK)



class FreelancerMilestoneViewSet(generics.RetrieveUpdateAPIView):
    """Viewset for updating terms acceptance by freelancer"""
    queryset = models.Milestone.objects.all()
    serializer_class = serializers.MilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset to only include contracts belonging to the authenticated freelancer"""
        return self.queryset.filter(contract__freelancer=self.request.user.freelancer)

    def get_object(self):
        """Retrieve and return the contract by ID belonging to the authenticated freelancer"""
        queryset = self.get_queryset()
        obj = generics.get_object_or_404(queryset, pk=self.kwargs.get('pk'))
        self.check_object_permissions(self.request, obj)
        return obj

    def put(self, request, *args, **kwargs):
        """Block PUT method to prevent full updates"""
        raise MethodNotAllowed("PUT method not allowed. Please use PATCH for partial updates.")
    def patch(self, request, *args, **kwargs):
        """Handle partial updates and update related milestones if they are pending"""
        milestone = self.get_object()
        milestone_update = milestone.milestone_update
        if(milestone_update):
            milestone_update.amount = milestone.amount
            milestone_update.due_date = milestone.due_date
            milestone_update.title = milestone.title
            milestone_update.description = milestone.description
            milestone_update.save()
            milestone.delete()
        else:
            serializer = self.get_serializer(milestone, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(status=status.HTTP_200_OK)



class FreelancerContractListViewSet(viewsets.ModelViewSet):
    """Viewset for listing contracts associated with the authenticated freelancer"""
    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retrieve and return the contracts for the authenticated freelancer"""
        return models.Contract.objects.filter(freelancer=self.request.user.freelancer)

class CounterOfferViewSet(viewsets.ModelViewSet):
    queryset = models.CounterOffer.objects.all()
    serializer_class = serializers.CounterOfferSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Automatically set the sender to the requesting user
        serializer.save(sender=self.request.user)

    def get_queryset(self):
        """
        Optionally restricts the returned counter offers to a given user.
        """
        user = self.request.user
        return models.CounterOffer.objects.filter(sender=user)  # Adjust this filter to include contracts related to the user as needed



class MileStoneViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.MilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_client = getattr(user, 'client', None)
        user_freelancer = getattr(user, 'freelancer', None)
        if user_client:
            return models.Milestone.objects.filter(contract__client=user_client)
        if user_freelancer:
            return models.Milestone.objects.filter(contract__freelancer=user_freelancer)
        return models.Milestone.objects.none()

    def perform_create(self, serializer):
        contract = serializer.validated_data.get('contract')
        user_client = getattr(self.request.user, 'client', None)
        if not user_client or contract.client != user_client:
            raise PermissionDenied('You do not own this contract.')
        serializer.save()

class CounterOfferMileStoneViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.CounterOfferMilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_client = getattr(user, 'client', None)
        user_freelancer = getattr(user, 'freelancer', None)
        if user_client:
            return models.CounterOfferMilestone.objects.filter(counter_offer__contract__client=user_client)
        if user_freelancer:
            return models.CounterOfferMilestone.objects.filter(counter_offer__contract__freelancer=user_freelancer)
        return models.CounterOfferMilestone.objects.none()

class CounterOfferViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request, contract_id=None):
        """
        This method handles GET requests to retrieve all counter offers related to a specific contract.
        """
        counter_offers = models.CounterOffer.objects.filter(contract_id=contract_id)
        serializer = serializers.CounterOfferSerializer(counter_offers, many=True)
        return Response(serializer.data)

class MilestoneByProjectView(generics.ListAPIView):
    """View to return milestones based on project_id"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.MilestoneSerializer

    def get_queryset(self):
        # Get project_id from the URL kwargs
        project_id = self.kwargs.get('project_id')

        # Filter contracts by project_id
        contracts = models.Contract.objects.filter(project_id=project_id)

        # Return milestones related to the contracts of the given project
        return models.Milestone.objects.filter(contract__in=contracts)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"detail": "No milestones found for the given project."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FreelancerMilestoneByProjectView(generics.ListAPIView):
    """View to return freelancer milestones based on project_id"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.MilestoneSerializer

    def get_queryset(self):
        # Get project_id from the URL kwargs
        project_id = self.kwargs.get('project_id')
        contracts = models.Contract.objects.filter(project_id=project_id, freelancer=self.request.user.freelancer)

        # Return milestones related to the contracts of the given project
        return models.Milestone.objects.filter(contract__in=contracts)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"detail": "No milestones found for the given project."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class FreelancerContractByProjectView(generics.ListAPIView):
    """
    View to return freelancer contracts based on project_id.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.ContractSerializer

    def get_queryset(self):
        # Get project_id from the URL kwargs
        project_id = self.kwargs.get('project_id')

        # Filter contracts by project_id and freelancer
        return models.Contract.objects.filter(
            project_id=project_id,
            freelancer=self.request.user.freelancer
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Handle case when no contracts are found
        if not queryset.exists():
            return Response(
                {"detail": "No Contract found for the given project."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Serialize and return the data
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CounterOfferView(viewsets.ModelViewSet):
    serializer_class = serializers.CounterOfferSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_client = getattr(user, 'client', None)
        user_freelancer = getattr(user, 'freelancer', None)
        if user_client:
            return models.CounterOffer.objects.filter(contract__client=user_client)
        if user_freelancer:
            return models.CounterOffer.objects.filter(contract__freelancer=user_freelancer)
        return models.CounterOffer.objects.none()

class DisputeViewSet(viewsets.ModelViewSet):
    """Viewset for managing disputes between client and freelancer"""
    serializer_class = serializers.DisputeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_client = getattr(user, 'client', None)
        user_freelancer = getattr(user, 'freelancer', None)
        if user_client:
            return models.Dispute.objects.filter(contract__client=user_client)
        if user_freelancer:
            return models.Dispute.objects.filter(contract__freelancer=user_freelancer)
        return models.Dispute.objects.none()

    def perform_create(self, serializer):
        """Create a dispute, setting the client, freelancer, and created_by fields automatically"""
        contract = serializer.validated_data.get('contract')
        milestone = serializer.validated_data.get('milestone', None)
        return_type = serializer.validated_data.get('return_type')
        user = self.request.user

        if models.Dispute.objects.filter(
            contract=contract, milestone=milestone, status='open'
        ).exists():
            raise ValidationError('An open dispute already exists for this contract.')

        return_amount = serializer.validated_data.get('return_amount')
        if return_type != 'full' and return_amount is not None:
            max_amount = milestone.amount if milestone else contract.amount_agreed
            if return_amount <= 0 or return_amount > max_amount:
                raise ValidationError(
                    {'return_amount': f'Must be greater than 0 and at most {max_amount}.'}
                )

        # Determine if the user is a client or freelancer associated with the contract
        try:
            # Safely retrieve `client` and `freelancer` attributes if they exist
            user_client = getattr(user, 'client', None)
            user_freelancer = getattr(user, 'freelancer', None)
            if user_client and user_client == contract.client:
                dispute = serializer.save(
                    client=user_client,
                    freelancer=contract.freelancer,
                    created_by=user,
                )
            elif user_freelancer and user_freelancer == contract.freelancer:
                dispute = serializer.save(
                    client=contract.client,
                    freelancer=user_freelancer,
                    created_by=user,
                )
            else:
                raise PermissionError("User is not authorized to create a dispute for this contract.")
            dispute_reciever = None
            if(user_client):
                dispute_reciever = contract.freelancer
            else:   
                dispute_reciever = contract.client
            notification_description = f"A dispute has been created for contract {contract.title}."

            models.Notification.objects.create(
                    user=dispute_reciever,
                    type='alert',
                    title=f"Dispute Created",
                    description=notification_description
            )
            models.Notification.objects.create(
                    user=dispute.created_by,
                    type='alert',
                    title=f"Dispute Created",
                    description=f"You have created a dispute for contract {contract.title}"
            )
            subject = "Dispute Created!"
    
            # HTML content for the email
            html_content = f"""
            <html>
                <body>
                    <p>{notification_description}</p>
                </body>
            </html>
            """
            
            # Call send_email function with the recipient email, subject, and HTML content
            send_email(dispute_reciever.email , subject, html_content)
        except PermissionError as e:
            raise PermissionError("You are not authorized to initiate a dispute for this contract.")

        except Exception as e:
            logger.exception("Unexpected error creating dispute")
            raise Exception("An error occurred while creating the dispute. Please try again later.")
        if milestone:
            milestone.status = "inDispute"
            milestone.save()
            if (return_type == "full"):
                print("in full milestone",milestone.amount)
                dispute.return_amount= milestone.amount
                dispute.save()
        else:
            contract.status = "inDispute"
            contract.save()
            if (return_type == "full"):
                print("in full contract",contract.amount_agreed)
                dispute.return_amount= contract.amount_agreed
                dispute.save()
        # Handle supporting documents
        supporting_documents_data = self.request.FILES.getlist('supporting_documents')
        for doc in supporting_documents_data:
            supporting_document = models.SupportingDocument.objects.create(
                file=doc,
                uploaded_by=user,
                dispute=dispute
            )
            dispute.supporting_documents.add(supporting_document)

    def update(self, request, *args, **kwargs):
        """Prevent updates to certain fields"""
        return_type = self.request.data.get('return_type',None)
        instance = self.get_object()
        if 'created_by' in request.data or 'client' in request.data or 'freelancer' in request.data:
            raise PermissionDenied("You do not have permission to update these fields.")
        
        # Handle supporting documents update if needed
        if 'supporting_documents' in request.FILES:
            supporting_documents_data = request.FILES.getlist('supporting_documents')
            for doc in supporting_documents_data:
                supporting_document = models.SupportingDocument.objects.create(
                    file=doc,
                    uploaded_by=request.user,
                    dispute=instance
                )
                instance.supporting_documents.add(supporting_document)
        return_amount = request.data.get('return_amount')
        if return_amount is not None and return_type != 'full':
            try:
                ra = Decimal(str(return_amount))
            except InvalidOperation:
                raise ValidationError({'return_amount': 'Invalid amount.'})
            max_amount = instance.milestone.amount if instance.milestone else instance.contract.amount_agreed
            if ra <= 0 or ra > max_amount:
                raise ValidationError(
                    {'return_amount': f'Must be greater than 0 and at most {max_amount}.'}
                )

        milestone = None
        if return_type and return_type == 'full':
            contract = models.Contract.objects.get(pk=instance.contract.id)
            if instance.milestone:
                milestone = models.Milestone.objects.get(pk=instance.milestone.id)
            if milestone:
                instance.return_amount = milestone.amount
            else:
                instance.return_amount = contract.amount_agreed
            instance.save()

        if 'status' in request.data:
            contract = models.Contract.objects.get(pk=instance.contract.id)
            if instance.milestone:
                milestone = models.Milestone.objects.get(pk=instance.milestone.id)
            new_status = request.data.get('status')
            if new_status in ('resolved', 'cancelled'):
                if milestone:
                    milestone.status = 'active'
                    milestone.save()
                contract.status = 'active'
                contract.save()
                models.DrcForwardedDisputes.objects.filter(dispute=instance).update(solved=True)
        return super().update(request, *args, **kwargs)

class DisputeResponseViewSet(viewsets.ModelViewSet):
    """Viewset for managing dispute responses between client and freelancer"""
    queryset = models.DisputeResponse.objects.all()
    serializer_class = serializers.DisputeResponseSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a dispute, setting the client, freelancer, and created_by fields automatically"""
        dispute = serializer.validated_data.get('dispute')
        dispute_to_respond = self.request.data.get('dispute_response', None)
        return_type = serializer.validated_data.get('return_type')

        user = self.request.user

        return_amount = serializer.validated_data.get('return_amount')
        if return_type != 'full' and return_amount is not None:
            milestone = dispute.milestone
            max_amount = milestone.amount if milestone else dispute.contract.amount_agreed
            if return_amount <= 0 or return_amount > max_amount:
                raise ValidationError(
                    {'return_amount': f'Must be greater than 0 and at most {max_amount}.'}
                )

        try:
            user_client = getattr(user, 'client', None)
            user_freelancer = getattr(user, 'freelancer', None)
        # Determine if the user is a client or freelancer associated with the contract
            if user_client and user_client == dispute.contract.client:
                new_dispute_response = serializer.save(
                created_by=user,
                )
            elif user_freelancer and user_freelancer == dispute.contract.freelancer:
                new_dispute_response = serializer.save(
                created_by=user,
                )
      
            else:
                raise PermissionDenied("You do not have permission to create a dispute response for this contract.")
            dispute_response_sender = None
            if(user_client):
                dispute_response_sender = dispute.client
            else:   
                dispute_response_sender = dispute.freelancer
            notification_description = f"A dispute response has been created for dispute {dispute.title}."
            email_message = f"You have a response for dispute {dispute.title}"
            
            models.Notification.objects.create(
                    user=dispute_response_sender,
                    type='alert',
                    title=f"Dispute Response Created",
                    description=notification_description
            )
            models.Notification.objects.create(
                    user=dispute.created_by,
                    type='alert',
                    title=f"Dispute got response",
                    description=f"You have a response for dispute {dispute.title}"
            )
            subject = "Dispute got Response!"
    
            # HTML content for the email
            html_content = f"""
            <html>
                <body>
                    <p>{email_message}</p>
                </body>
            </html>
            """
            
            # Call send_email function with the recipient email, subject, and HTML content
            send_email(dispute.created_by.email , subject, html_content)
        except PermissionError as e:
            raise PermissionError("You are not authorized to initiate a dispute for this contract.")

        except Exception as e:
            logger.exception("Unexpected error creating dispute response")
            raise Exception("An error occurred while creating the dispute response. Please try again later.")
        if dispute_to_respond:
            dispute_response_ = models.DisputeResponse.objects.get(pk=dispute_to_respond)
            if dispute_response_.dispute_id != dispute.id:
                raise ValidationError('The cited response does not belong to this dispute.')
            if dispute_response_.created_by == user:
                raise ValidationError('You cannot reply to your own response.')
            dispute_response_.got_response = True
            dispute_response_.save()
            if(return_type == "full"):
                if(dispute_response_.milestone):
                    new_dispute_response.return_amount = dispute_response_.dispute.milestone.amount
                else:
                    new_dispute_response.return_amount = dispute_response_.dispute.contract.amount_agreed
        else:
            dispute.contract.got_response = True
            dispute.contract.save()
            if(return_type == "full"):
                if(dispute.milestone):
                    new_dispute_response.return_amount = dispute.milestone.amount
                else:
                    new_dispute_response.return_amount = dispute.contract.amount_agreed

       

            
        # Handle supporting documents
        supporting_documents_data = self.request.FILES.getlist('supporting-documents')
        for doc in supporting_documents_data:
            dispute = None
            if dispute_to_respond:
                dispute = models.DisputeResponse.objects.get(pk = dispute_to_respond)
            else:
                dispute = new_dispute_response.dispute

            supporting_document = models.SupportingDocument.objects.create(
                file=doc,
                uploaded_by=user,
                dispute=dispute
                )
            new_dispute_response.dispute.supporting_documents.add(supporting_document)

    def update(self, request, *args, **kwargs):
        """Prevent updates to certain fields"""
        instance = self.get_object()
        return_type = self.request.data.get('return_type', None)

        if 'created_by' in request.data or 'client' in request.data or 'freelancer' in request.data:
            raise PermissionDenied("You do not have permission to update these fields.")

        return_amount = request.data.get('return_amount')
        if return_amount is not None and return_type != 'full':
            try:
                ra = Decimal(str(return_amount))
            except InvalidOperation:
                raise ValidationError({'return_amount': 'Invalid amount.'})
            milestone = instance.dispute.milestone
            max_amount = milestone.amount if milestone else instance.dispute.contract.amount_agreed
            if ra <= 0 or ra > max_amount:
                raise ValidationError(
                    {'return_amount': f'Must be greater than 0 and at most {max_amount}.'}
                )

        if return_type == 'full':
            if instance.dispute.milestone:
                instance.return_amount = instance.dispute.milestone.amount
            else:
                instance.return_amount = instance.dispute.contract.amount_agreed

        # Handle supporting documents update if needed
        if 'supporting_documents' in request.data:
            supporting_documents_data = request.data.get('supporting_documents')
            for doc_id in supporting_documents_data:
                document_instance = models.SupportingDocument.objects.get(pk=doc_id)
                instance.supporting_documents.add(document_instance)
                instance.save()
             # Optionally remove supporting_documents key from request.data
            del request.data['supporting_documents']  # Use this line if needed
        return super().update(request, *args, **kwargs)



class DisputeCheckView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        dispute_id = request.query_params.get('dispute_id')
        
        if not dispute_id:
            return Response({"detail": "Dispute ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            dispute = models.Dispute.objects.get(id=dispute_id)
        except models.Dispute.DoesNotExist:
            return Response({"detail": "Dispute not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if the dispute exists in DrcForwardedDisputes
        forwarded_dispute = models.DrcForwardedDisputes.objects.filter(dispute=dispute).first()
        
        if forwarded_dispute:
            return Response({"is_in_drc_forwarded": True}, status=status.HTTP_200_OK)
        else:
            return Response({"is_in_drc_forwarded": False}, status=status.HTTP_200_OK)



class DisputeListView(generics.ListAPIView):
    """
    This view returns a list of disputes associated with a contract
    """
    serializer_class = serializers.DisputeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        contract_id = self.kwargs.get('contract_id')
        return models.Dispute.objects.filter(contract_id=contract_id)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"detail": "No disputes found for this contract."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DisputeResponseListView(generics.ListAPIView):
    """
    This view returns a list of dispute responses associated with a contract.
    """
    serializer_class = serializers.DisputeResponseSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        contract_id = self.kwargs.get('contract_id')
        return models.DisputeResponse.objects.filter(dispute__contract_id=contract_id)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"detail": "No dispute responses found for this contract."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class IsDisputeManager(permissions.BasePermission):
    """
    Custom permission to allow only dispute managers to perform actions.
    """
    
    def has_permission(self, request, view):
        # Check if the user is authenticated and is a dispute manager
        return request.user.is_authenticated and models.DisputeManager.objects.filter(id=request.user.id).exists()

class ResolvedDrcViewSet(viewsets.ModelViewSet):
    """Viewset for resolving disputes forwarded to DRC"""
    queryset = models.DrcResolvedDisputes.objects.all()
    serializer_class = serializers.DrcResolvedDisputesSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsDisputeManager]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # Get created dispute object
        drc_resolved_dispute = serializer.instance

        # Send Notification
        client = drc_resolved_dispute.drc_forwarded.dispute.client 
        freelancer = drc_resolved_dispute.drc_forwarded.dispute.freelancer 
        # Format notification and email details
        winner = (
            "Client" if drc_resolved_dispute.winner == "client" else "Freelancer"
        )
        # Initialize the notification description
        notification_description = "Dispute Resolution Summary:\n"

        # Add fields conditionally
        if drc_resolved_dispute.title:
            notification_description += f"- Title: {drc_resolved_dispute.title}\n"
        if drc_resolved_dispute.winner:
            notification_description += f"- Winner: {winner}\n"
        if drc_resolved_dispute.return_type:
            notification_description += f"- Return Type: {drc_resolved_dispute.return_type}\n"
        if drc_resolved_dispute.return_amount:
            notification_description += f"- Return Amount: {drc_resolved_dispute.return_amount}\n"
        if drc_resolved_dispute.comment:
            notification_description += f"- Comment: {drc_resolved_dispute.comment}\n"
        models.Notification.objects.create(
                    user=client,
                    type='alert',
                    title=f"Your dispute has been resolved.",
                    description=notification_description
            )
        models.Notification.objects.create(
                    user=freelancer,
                    type='alert',
                    title=f"Your dispute has been resolved.",
                    description=notification_description
            )
        models.Notification.objects.create(
                    user=request.user,
                    type='alert',
                    title=f"Dispute Resolved",
                    description=notification_description
            )
        # HTML content for the email   
        html_content = f"""
        <html>
            <body>
                <p>{notification_description}</p>
            </body>
        </html>
        """
        # Call send_email function with the recipient email, subject, and HTML content
        send_email(client.email , "Dispute Resolved", html_content)
        send_email(freelancer.email , "Dispute Resolved", html_content)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)



class SupportingDocumentView(viewsets.ModelViewSet):
    queryset = models.SupportingDocument.objects.all()
    serializer_class = serializers.SupportingDocumentSerializer
    permission_classes = [IsAuthenticated]


class DrcForwardedDisputesViewSet(viewsets.ModelViewSet):
    queryset = models.DrcForwardedDisputes.objects.all()
    serializer_class = serializers.DRCFowrwardSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_least_assigned_manager(self):
        """Select the dispute manager who has the fewest disputes recently or is eligible based on `dispute_per_week`."""
        one_week_ago = timezone.now() - timedelta(days=7)

        # Get eligible dispute managers based on their weekly limit
        eligible_managers = models.DisputeManager.objects.annotate(
            weekly_assigned_disputes=Count(
                'drcforwardeddisputes', 
                filter=Q(drcforwardeddisputes__created_at__gte=one_week_ago)
            )
        ).filter(weekly_assigned_disputes__lt=F('dispute_per_week'))

        # Sort by unresolved disputes and earliest resolution times
        eligible_managers = eligible_managers.annotate(
            unresolved_disputes=Count(
                'drcforwardeddisputes', 
                filter=Q(drcforwardeddisputes__solved=False)
            )
        ).order_by('unresolved_disputes', 'drcforwardeddisputes__updated_at')

        return eligible_managers.first()

    def create(self, request, *args, **kwargs):
        # Get the best-suited dispute manager based on load and recent activity
        manager = self.get_least_assigned_manager()
        dispute_id = request.data.get('dispute')
        dispute = models.Dispute.objects.get(id=dispute_id)
        user = self.request.user
        try:
            user_client = getattr(user, 'client', None)
            user_freelancer = getattr(user, 'freelancer', None)
        except PermissionError as e:
            # Handle the case where the user is neither a client nor a freelancer in this contract
            print(f"PermissionError: {e}")
            raise PermissionError("You are not authorized to initiate a dispute for this contract.")
        if not manager:
            return Response(
                {"error": "No dispute manager available within the weekly assignment limit."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Prepare data with selected manager
        data = request.data.copy()
        data['dispute_manager'] = manager.id

        # Serialize and save the new dispute assignment
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        email_message = f"Dispute {dispute.title} has been forwarded to dispute resolution center."
        dispute_response_sender = None
        if(user_client):
            dispute_response_sender = dispute.client
        else:   
            dispute_response_sender = dispute.freelancer
        models.Notification.objects.create(
                user=dispute_response_sender,
                type='alert',
                title=f"Dispute Response Created",
                description=email_message
        )
        models.Notification.objects.create(
                user=dispute.created_by,
                type='alert',
                title=f"Dispute got response",
                description=email_message
        )
        models.Notification.objects.create(
                user=manager,
                type='alert',
                title=f"Dispute Forwarded to DRC.",
                description=email_message
        )
        subject = "Dispute got Response!"

        # HTML content for the email
        html_content = f"""
        <html>
            <body>
                <p>{email_message}</p>
            </body>
        </html>
        """
        
        # Call send_email function with the recipient email, subject, and HTML content
        send_email(dispute.created_by.email , subject, html_content)
        send_email(manager.email , "Dispute Forwarded to DRC.", html_content)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        """Custom save logic for creating a DRC forwarded dispute."""
        serializer.save()



class DisputeManagerDisputesView(generics.ListAPIView):
    serializer_class = serializers.DRCFowrwardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Ensure the user is a DisputeManager
        if not hasattr(self.request.user, 'disputemanager'):
            raise PermissionDenied("You do not have permission to view these disputes.")

        # Filter disputes for the logged-in dispute manager
        return models.DrcForwardedDisputes.objects.filter(dispute_manager=self.request.user.disputemanager)

    def list(self, request, *args, **kwargs):
        # Override list to return a custom response format if needed
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "latest_disputes": serializer.data
        })


class MilestoneDisputeListView(generics.ListAPIView):
    """
    This view returns a list of disputes associated with a milestone
    """
    serializer_class = serializers.DisputeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        milestone_id = self.kwargs.get('milestone_id')
        return models.Dispute.objects.filter(milestone_id=milestone_id)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"detail": "No disputes found for this milestone."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelDisputeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, dispute_id):
        try:
            dispute = models.Dispute.objects.select_related('contract', 'milestone').get(id=dispute_id)
        except models.Dispute.DoesNotExist:
            return Response({'error': 'Dispute not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        user_client = getattr(user, 'client', None)
        user_freelancer = getattr(user, 'freelancer', None)
        is_party = (
            (user_client and user_client == dispute.contract.client) or
            (user_freelancer and user_freelancer == dispute.contract.freelancer)
        )
        if not is_party:
            return Response({'error': 'You are not a party to this dispute.'}, status=status.HTTP_403_FORBIDDEN)

        if dispute.status != 'open':
            return Response(
                {'error': f'Dispute is already {dispute.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispute.status = 'cancelled'
        dispute.save(update_fields=['status'])

        if dispute.milestone:
            dispute.milestone.status = 'active'
            dispute.milestone.save(update_fields=['status'])
        elif dispute.contract:
            dispute.contract.status = 'active'
            dispute.contract.save(update_fields=['status'])

        return Response({'status': 'cancelled'}, status=status.HTTP_200_OK)



class EscrowViewSet(viewsets.ModelViewSet):
    """Viewset for managing escrows"""
    queryset = models.Escrow.objects.all()
    serializer_class = serializers.EscrowSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create an escrow, ensuring the contract and potential milestone are valid"""
        contract_id = self.request.data.get('contract')
        milestone_id = self.request.data.get('milestone')

        if not contract_id:
            raise PermissionDenied("Contract ID must be provided.")

        # Ensure the contract exists and belongs to the current client
        contract = generics.get_object_or_404(models.Contract, pk=contract_id, client=self.request.user.client)

        # Check if the contract is milestone-based
        milestone = None
        if contract.milestone_based:
            if milestone_id:
                # Ensure the milestone exists and belongs to the contract
                milestone = generics.get_object_or_404(models.Milestone, pk=milestone_id, contract=contract)
            else:
                raise PermissionDenied("Milestone ID must be provided for milestone-based contracts.")
        else:
            if milestone_id:
                raise PermissionDenied("Milestone ID should not be provided for one-time payment contracts.")

        serializer.save(contract=contract, milestone=milestone)

    def update(self, request, *args, **kwargs):
        escrow = self.get_object()
        contract = escrow.contract

        if contract.client != request.user.client:
            raise PermissionDenied("You do not have permission to release funds for this escrow.")

        # # Prevent clients and freelancers from updating deposit_confirmed
        # if 'deposit_confirmed' in request.data:
        #     raise PermissionDenied("You do not have permission to update deposit_confirmed.")

        if 'status' in request.data and request.data['status'] == 'release':
            escrow.release()
            request.data['status'] = 'released'

        serializer = self.get_serializer(escrow, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class CancelContractView(APIView):
    """
    POST /api/contracts/{id}/cancel/

    Client cancels a contract. Rules:
    - Only the client who owns the contract can cancel.
    - Cannot cancel if status is already cancelled or completed.
    - Cannot cancel if any open dispute exists on the contract.
    - Funded (deposit_confirmed=True, status=Pending) escrows are refunded to the client via Chapa.
    - Unfunded escrows are deleted.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.db import transaction as db_transaction

        contract = models.Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({'error': 'Contract not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            client = models.Client.objects.get(pk=request.user.pk)
        except models.Client.DoesNotExist:
            return Response({'error': 'Only clients can cancel contracts.'}, status=status.HTTP_403_FORBIDDEN)

        if contract.client != client:
            return Response({'error': 'You do not own this contract.'}, status=status.HTTP_403_FORBIDDEN)

        if contract.status in ('canceled', 'completed'):
            return Response(
                {'error': f'Contract is already {contract.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fix 1: block cancellation of active contracts — freelancer may be working
        if contract.status == 'active':
            return Response(
                {'error': 'Contract is active. Open a dispute if you need to exit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if models.Dispute.objects.filter(contract=contract, status='open').exists():
            return Response(
                {'error': 'Contract has an open dispute. Resolve or close it before cancelling.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Fix 2: lock escrow rows inside a transaction to prevent concurrent double-refund
        refund_errors = []
        with db_transaction.atomic():
            escrows = models.Escrow.objects.select_for_update().filter(contract=contract, status='Pending')
            for escrow in escrows:
                if escrow.deposit_confirmed:
                    escrow.refund()
                    if escrow.status != 'Refunded':
                        refund_errors.append(str(escrow.id))
                else:
                    escrow.delete()

            contract.status = 'canceled'
            contract.save(update_fields=['status'])

        # Notify both parties
        freelancer = contract.freelancer
        msg = f'Contract "{contract.title}" has been cancelled by the client.'
        html = f'<html><body><p>{msg}</p></body></html>'
        send_email(client.email, 'Contract cancelled', html)
        if freelancer:
            send_email(freelancer.email, 'Contract cancelled', html)

        response_data = {'status': 'canceled'}
        if refund_errors:
            response_data['refund_warnings'] = (
                f'Chapa refund failed for escrow(s): {", ".join(refund_errors)}. '
                'These escrows are marked RefundFailed in the admin — manual intervention required.'
            )
        return Response(response_data, status=status.HTTP_200_OK)


class FreelancerCancelContractView(APIView):
    """
    POST /api/contracts/{id}/freelancer-cancel/

    Freelancer cancels a contract they have accepted, but only while no escrow
    has been funded yet (deposit_confirmed=False on all escrows). Once the client
    has paid into escrow the contract is active and a dispute is required instead.

    Rules:
    - Must be the freelancer on this contract.
    - Contract status must be 'pending' or 'accepted' (not yet active/completed/cancelled).
    - No escrow may be funded (deposit_confirmed=True).
    - No open disputes on the contract.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = models.Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({'error': 'Contract not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            freelancer = models.Freelancer.objects.get(pk=request.user.pk)
        except models.Freelancer.DoesNotExist:
            return Response({'error': 'Only freelancers can use this endpoint.'}, status=status.HTTP_403_FORBIDDEN)

        if contract.freelancer != freelancer:
            return Response({'error': 'You are not the freelancer on this contract.'}, status=status.HTTP_403_FORBIDDEN)

        if contract.status in ('canceled', 'completed'):
            return Response(
                {'error': f'Contract is already {contract.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if contract.status == 'active':
            return Response(
                {'error': 'Contract is already active with funded escrow. Open a dispute if you need to exit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if models.Dispute.objects.filter(contract=contract, status='open').exists():
            return Response(
                {'error': 'Contract has an open dispute. Resolve it before cancelling.'},
                status=status.HTTP_409_CONFLICT,
            )

        if models.Escrow.objects.filter(contract=contract, deposit_confirmed=True).exists():
            return Response(
                {'error': 'Escrow has already been funded. Open a dispute if you need to exit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Safe to cancel — delete unfunded escrow rows and mark cancelled
        models.Escrow.objects.filter(contract=contract).delete()
        contract.status = 'canceled'
        contract.save(update_fields=['status'])

        msg = f'Contract "{contract.title}" has been cancelled by the freelancer.'
        html = f'<html><body><p>{msg}</p></body></html>'
        if contract.client:
            send_email(contract.client.email, 'Contract cancelled', html)
        send_email(freelancer.email, 'Contract cancelled', html)

        return Response({'status': 'canceled'}, status=status.HTTP_200_OK)


class ApproveMilestoneView(APIView):
    """
    POST /api/milestones/{id}/approve/

    Client approves a milestone that is in pendingApproval status.
    Sets milestone to completed and triggers escrow release (payout to freelancer).
    If all milestones are now completed, the contract is also marked completed.

    Rules:
    - Must be the client on this contract.
    - Milestone must be in pendingApproval status.
    - No open dispute on this milestone.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        milestone = models.Milestone.objects.filter(pk=pk).select_related('contract').first()
        if not milestone:
            return Response({'error': 'Milestone not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            client = models.Client.objects.get(pk=request.user.pk)
        except models.Client.DoesNotExist:
            return Response({'error': 'Only clients can approve milestones.'}, status=status.HTTP_403_FORBIDDEN)

        if milestone.contract.client != client:
            return Response({'error': 'You do not own this contract.'}, status=status.HTTP_403_FORBIDDEN)

        if milestone.status != 'pendingApproval':
            return Response(
                {'error': f'Milestone is not pending approval (current status: {milestone.status}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if models.Dispute.objects.filter(
            contract=milestone.contract, milestone=milestone, status='open'
        ).exists():
            return Response(
                {'error': 'Milestone has an open dispute. Resolve it before approving.'},
                status=status.HTTP_409_CONFLICT,
            )

        milestone.status = 'completed'
        milestone.save(update_fields=['status'])

        escrow = models.Escrow.objects.filter(
            contract=milestone.contract, milestone=milestone
        ).first()
        if escrow:
            escrow.release()

        # If all milestones on this contract are now completed, close the contract too
        has_incomplete = models.Milestone.objects.filter(
            contract=milestone.contract
        ).exclude(status='completed').exists()
        if not has_incomplete:
            milestone.contract.status = 'completed'
            milestone.contract.save(update_fields=['status'])

        return Response({'status': 'completed'}, status=status.HTTP_200_OK)


class CancelMilestoneView(APIView):
    """
    POST /api/milestones/{id}/cancel/

    Client cancels a single milestone without cancelling the whole contract.
    Only allowed before work has started (pending or accepted status).
    If the milestone's escrow is funded, a Chapa refund is initiated.
    If unfunded, the escrow row is deleted.
    The contract remains active — other milestones are unaffected.

    Rules:
    - Must be the client on this contract.
    - Milestone must be pending or accepted (not active/in-progress).
    - No open dispute on this milestone.
    - Milestone must not already be completed or cancelled.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        milestone = models.Milestone.objects.filter(pk=pk).select_related('contract').first()
        if not milestone:
            return Response({'error': 'Milestone not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            client = models.Client.objects.get(pk=request.user.pk)
        except models.Client.DoesNotExist:
            return Response({'error': 'Only clients can cancel milestones.'}, status=status.HTTP_403_FORBIDDEN)

        if milestone.contract.client != client:
            return Response({'error': 'You do not own this contract.'}, status=status.HTTP_403_FORBIDDEN)

        if milestone.status in ('completed', 'cancelled'):
            return Response(
                {'error': f'Milestone is already {milestone.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if milestone.status in ('active', 'pendingApproval', 'inDispute'):
            return Response(
                {'error': 'Work has already started on this milestone. Open a dispute if you need to exit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if models.Dispute.objects.filter(
            contract=milestone.contract, milestone=milestone, status='open'
        ).exists():
            return Response(
                {'error': 'Milestone has an open dispute. Resolve it before cancelling.'},
                status=status.HTTP_409_CONFLICT,
            )

        escrow = models.Escrow.objects.filter(
            contract=milestone.contract, milestone=milestone
        ).first()

        refund_warning = None
        if escrow:
            if escrow.deposit_confirmed and escrow.status == 'Pending':
                escrow.refund()
                if escrow.status == 'RefundFailed':
                    refund_warning = (
                        f'Chapa refund failed for escrow {escrow.id}. '
                        'It is marked RefundFailed in admin — manual intervention required.'
                    )
            else:
                escrow.delete()

        milestone.status = 'cancelled'
        milestone.save(update_fields=['status'])

        response_data = {'status': 'cancelled'}
        if refund_warning:
            response_data['refund_warning'] = refund_warning
        return Response(response_data, status=status.HTTP_200_OK)


class DepositConfirmedUpdateView(generics.UpdateAPIView):
    """Partial update for deposit_confirmed field"""
    queryset = models.Escrow.objects.all()
    serializer_class = serializers.DepositConfirmedUpdateSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        # Ensure only non-client and non-freelancer users can update deposit_confirmed
        user = request.user
        if hasattr(user, 'client') or hasattr(user, 'freelancer'):
            raise PermissionDenied("You do not have permission to update deposit_confirmed.")

        return super().update(request, *args, **kwargs)


# # Additional Views for specific routes

class EscrowListView(generics.ListCreateAPIView):
    """View for listing and creating escrows for a specific contract"""
    queryset = models.Escrow.objects.all()
    serializer_class = serializers.EscrowSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        contract_id = self.kwargs.get('contract_pk')
        contract = generics.get_object_or_404(models.Contract, pk=contract_id)
        return self.queryset.filter(contract = contract)

class EscrowMilestoneListView(generics.ListCreateAPIView):
    """View for listing and creating escrows for a specific contract"""
    queryset = models.Escrow.objects.all()
    serializer_class = serializers.EscrowSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        milestone_id = self.kwargs.get('milestone_pk')
        milestone = generics.get_object_or_404(models.Milestone, pk=milestone_id)
        return self.queryset.filter(milestone = milestone)

class ProjectFreelancersView(APIView):
    """
    View to return freelancers associated with a given project.
    """

    def get(self, request, project_id):
        try:
            # Fetch the project by ID
            project = models.Project.objects.get(id=project_id)

            # Find contracts associated with this project
            contracts = models.Contract.objects.filter(project=project)

            # Extract freelancers from these contracts
            freelancers = [contract.freelancer for contract in contracts]

            # Serialize the freelancers
            serializer = serializers.FreelancerSerializer(freelancers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except models.Project.DoesNotExist:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)


class ProjectMilestonesView(APIView):
    """
    View to return milestones associated with a given project.
    """

    def get(self, request, project_id):
        try:
            # Fetch the project by ID
            project = models.Project.objects.get(id=project_id)

            # Find contracts associated with this project
            contracts = models.Contract.objects.filter(project=project)

            # Get all milestones related to the contracts of this project
            milestones = models.Milestone.objects.filter(contract__in=contracts)

            # Serialize the milestones
            serializer = serializers.MilestoneSerializer(milestones, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except models.Project.DoesNotExist:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

class ActiveContractCheckView(APIView):
    """
    API view to check if a client has an active contract with a freelancer.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        freelancer_id = request.query_params.get('freelancer_id')
        client_id = request.query_params.get('client_id')

        if not freelancer_id or not client_id:
            return Response({"error": "Both freelancer_id and client_id are required."}, status=400)

        # Check if there's an active contract
        active_contract = models.Contract.objects.filter(
            freelancer_id=freelancer_id,
            client_id=client_id,
            status='active'
        ).exists()

        return Response({"active_contract": active_contract}, status=200)


# class EscrowDetailView(generics.RetrieveUpdateDestroyAPIView):
#     """View for retrieving, updating, or deleting a specific escrow"""
#     queryset = models.Escrow.objects.all()
#     serializer_class = serializers.EscrowSerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
        
#     def get_queryset(self):
#         contract_id = self.kwargs.get('contract_pk')
#         return self.queryset.filter(contract_id=contract_id)





# class EscrowMilestoneDetailView(generics.RetrieveUpdateDestroyAPIView):
#     """View for retrieving, updating, or deleting a specific escrow associated with a milestone"""
#     queryset = models.Escrow.objects.all()
#     serializer_class = serializers.EscrowSerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         contract_id = self.kwargs.get('contract_pk')
#         milestone_id = self.kwargs.get('milestone_pk')
#         return self.queryset.filter(contract_id=contract_id, milestone_id=milestone_id)


