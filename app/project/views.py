from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed
from project import serializers
from core import models
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Count, Q, F
from datetime import timedelta
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from .utils import send_email


class ProjectViewSet(viewsets.ModelViewSet):
    """View for managing projects of a client"""
    queryset = models.Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a project for a client"""
        client = models.Client.objects.get(email=self.request.user.email)
        
        # Check if a project with the same title already exists for the client
        if models.Project.objects.filter(client=client, title=serializer.validated_data['title']).exists():
            raise ValidationError({"title": "Title already used."})
        
        serializer.save(client=client)

    def list(self, request, *args, **kwargs):
        """List projects created by clients"""
        queryset = self.filter_queryset(self.get_queryset().filter(client=self.request.user.client))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single project created by a client"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_update(self, serializer):
        """Update a project for a client"""
        # Get the current project instance
        instance = self.get_object()
        client = models.Client.objects.get(email=self.request.user.email)
        
        # Check if another project with the same title exists for the client (excluding the current instance)
        if models.Project.objects.filter(client=client, title=serializer.validated_data['title']).exclude(id=instance.id).exists():
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
        
        # if 'status' in request.data and request.data['status'] == 'active':
        #     escrows = models.Escrow.objects.filter(contract = instance)
        #     if escrows.__len__()>0:
        #         if instance.is_escrow_fulfilled():
        #             instance.start_project()
        #             request.data['status'] = 'in_progress'
        #         else:
        #             return Response({'status': 'Escrow not fulfilled'}, status=status.HTTP_400_BAD_REQUEST)


        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
    """View for getting the list of contracts"""
    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


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
    """Viewset for managing disputes between client and freelancer"""
    queryset = models.Milestone.objects.all()
    serializer_class = serializers.MilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

class CounterOfferMileStoneViewSet(viewsets.ModelViewSet):
    """Viewset for managing disputes between client and freelancer"""
    queryset = models.CounterOfferMilestone.objects.all()
    serializer_class = serializers.CounterOfferMilestoneSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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
        print("freelancer is",self.request.user.freelancer)
        # Filter contracts by project_id
        contracts = models.Contract.objects.filter(project_id=project_id , freelancer=self.request.user.freelancer)

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
    """Viewset for managing disputes between client and freelancer"""
    queryset = models.CounterOffer.objects.all()
    serializer_class = serializers.CounterOfferSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

class DisputeViewSet(viewsets.ModelViewSet):
    """Viewset for managing disputes between client and freelancer"""
    queryset = models.Dispute.objects.all()
    serializer_class = serializers.DisputeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a dispute, setting the client, freelancer, and created_by fields automatically"""
        contract = serializer.validated_data.get('contract')
        milestone = serializer.validated_data.get('milestone', None)
        return_type = serializer.validated_data.get('return_type')
        user = self.request.user
        print("return type is ",return_type)
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
            # Handle the case where the user is neither a client nor a freelancer in this contract
            print(f"PermissionError: {e}")
            raise PermissionError("You are not authorized to initiate a dispute for this contract.")

        except Exception as e:
            # General exception handling
            print(f"An unexpected error occurred: {e}")
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
        milestone = None
        if return_type and return_type=="full":
            contract = models.Contract.objects.get(pk = instance.contract.id)
            if(instance.milestone):
                milestone = models.Milestone.objects.get(pk = instance.milestone.id)
            if (milestone):
                instance.return_amount= milestone.amount
            else:
                instance.return_amount= contract.amount_agreed
            instance.save()

        if 'status' in request.data:
            print("checking status .....")
            print("contract id is ",instance.contract.id)
            contract = models.Contract.objects.get(pk = instance.contract.id)
            if(instance.milestone):
                milestone = models.Milestone.objects.get(pk = instance.milestone.id)
            if (request.data.get('status') == 'resolved' or request.data.get('status') == 'cancelled'):
                if (milestone):
                    milestone.status = "active"
                    milestone.save()
                contract.status = "active"
                contract.save()
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
            # Handle the case where the user is neither a client nor a freelancer in this contract
            print(f"PermissionError: {e}")
            raise PermissionError("You are not authorized to initiate a dispute for this contract.")

        except Exception as e:
            # General exception handling
            print(f"An unexpected error occurred: {e}")
            raise Exception("An error occurred while creating the dispute response. Please try again later.")
        if dispute_to_respond:
            dispute_response_ = models.DisputeResponse.objects.get(pk = dispute_to_respond)
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
        return_type = self.request.data.get('return_type',None)

        if 'created_by' in request.data or 'client' in request.data or 'freelancer' in request.data:
            raise PermissionDenied("You do not have permission to update these fields.")
        if(return_type == "full"):
            if(instance.dispute.milestone):
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
        send_email(manager.email , "Dispute Frorwarded to DRC.", html_content)
        
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
    def patch(self, request, dispute_id):
        try:
            # Get the dispute by ID
            print("Dispute ID is", dispute_id)
            dispute = models.Dispute.objects.get(id=dispute_id)

            # Update the dispute status to resolved
            dispute.status = 'resolved'
            dispute.save()
            
            # Get the associated milestone or contract
            if dispute.milestone:
                milestone = dispute.milestone
                milestone.status = 'active'
                milestone.save()
            elif dispute.contract:  # Added check to handle cases where there is no milestone
                contract = dispute.contract
                contract.status = 'active'
                contract.save()
            else:
                return Response({'error': 'No milestone or contract associated with this dispute'}, status=status.HTTP_400_BAD_REQUEST)

            # Return success response
            return Response({'success': "Dispute Canceled"}, status=status.HTTP_200_OK)

        except models.Dispute.DoesNotExist:
            return Response({'error': 'Dispute not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



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


