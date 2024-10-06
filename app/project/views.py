from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed
from project import serializers
from core import models
from rest_framework.views import APIView

class ProjectViewSet(viewsets.ModelViewSet):
    """View for managing projects of a client"""
    queryset = models.Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a project for a client"""
        client = models.Client.objects.get(email=self.request.user.email)
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

        if not models.Client.objects.contains(pk= request.user.id):
            raise PermissionDenied("You do not have permission to update this contract.")
        if request.user.client != instance.client:
            raise PermissionDenied("You do not have permission to update this contract.")
        
        if 'status' in request.data and request.data['status'] == 'active':
            escrows = models.Escrow.objects.filter(contract = instance)
            if escrows.__len__()>0:
                if instance.is_escrow_fulfilled():
                    instance.start_project()
                    request.data['status'] = 'in_progress'
                else:
                    return Response({'status': 'Escrow not fulfilled'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

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
        user = self.request.user

        # Determine if the user is a client or freelancer associated with the contract
        if user.client == contract.client:
            dispute = serializer.save(
                client=user.client,
                freelancer=contract.freelancer,
                created_by=user,
            )
        elif user.freelancer == contract.freelancer:
            dispute = serializer.save(
                client=contract.client,
                freelancer=user.freelancer,
                created_by=user,
            )
      
        else:
            raise PermissionDenied("You do not have permission to create a dispute for this contract.")
        if milestone:
            milestone.status = "inDispute"
            milestone.save()
        else:
            contract.status = "inDispute"
            contract.save()
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

        return super().update(request, *args, **kwargs)


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