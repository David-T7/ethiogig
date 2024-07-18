from rest_framework import viewsets , generics ,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response 
from project import serializers
from core import models
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied , MethodNotAllowed


class ProjectViewSet(viewsets.ModelViewSet):
    """View for managing project of a client"""
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

        # Check if freelancer_accepted_terms is being updated by the freelancer
        if 'freelancer_accepted_terms' in request.data:
            raise PermissionDenied("You do not have permission to update freelancer_accepted_terms.")
        try:
            if request.user.client == instance.client:
                serializer = self.get_serializer(instance, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)
        except:
            raise PermissionDenied("You do not have permission to update this contract.")


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

class FreelancerContractDetialViewSet(generics.RetrieveAPIView):
    """Viewset for accepting terms by freelancer"""

    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated client's contract"""
        return models.Contract.objects.get(freelancer=self.request.user.freelancer)




class DisputeViewSet(viewsets.ModelViewSet):
    """Viewset for managing disputes between client and freelancer"""

    queryset = models.Dispute.objects.all()
    serializer_class = serializers.DisputeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a dispute, setting the client, freelancer, and created_by fields automatically"""
        contract = serializer.validated_data['contract']
        if self.request.user.client == contract.client:
            dispute = serializer.save(
                client=self.request.user.client,
                freelancer=contract.freelancer,
                created_by=self.request.user,
            )
        elif self.request.user.freelancer == contract.freelancer:
            dispute = serializer.save(
                client=contract.client,
                freelancer=self.request.user.freelancer,
                created_by=self.request.user,
            )
        else:
            raise PermissionDenied("You do not have permission to create a dispute for this contract.")

        # # Handle supporting documents
        supporting_documents_data = self.request.FILES.getlist('supporting_documents')
        for doc in supporting_documents_data:
            supporting_document = models.SupportingDocument.objects.create(file=doc , uploaded_by=self.request.user , dispute=dispute)
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
                supporting_document = models.SupportingDocument.objects.create(file=doc)
                instance.supporting_documents.add(supporting_document)

        return super().update(request, *args, **kwargs)