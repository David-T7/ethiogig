from django.shortcuts import render
from rest_framework import generics, authentication, permissions, status , viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from user.serializers import FreelancerSerializer, ClientSerializer, CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from core import models
from project.serializers import ProjectSerializer
from rest_framework.generics import get_object_or_404


def get_tokens_for_user(user):
    """Generate JWT tokens for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class CreateFreelancerView(generics.CreateAPIView):
    """Create a new freelancer in the system"""
    serializer_class = FreelancerSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        tokens = get_tokens_for_user(serializer.instance)
        return Response({**serializer.data, **tokens}, status=status.HTTP_201_CREATED, headers=headers)


class CreateClientView(generics.CreateAPIView):
    """Create a new client in the system"""
    serializer_class = ClientSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        tokens = get_tokens_for_user(serializer.instance)
        return Response({**serializer.data, **tokens}, status=status.HTTP_201_CREATED, headers=headers)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Obtain JWT token pair"""
    serializer_class = CustomTokenObtainPairSerializer


class ManageFreelancerView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated freelancer"""
    serializer_class = FreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated freelancer user"""
        return models.Freelancer.objects.get(email=self.request.user.email)


class ManageClientView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated client"""
    serializer_class = ClientSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated client user"""
        return models.Client.objects.get(email=self.request.user.email)


class RemoveFreelancerView(generics.DestroyAPIView):
    queryset = models.Freelancer.objects.all()
    serializer_class = FreelancerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.queryset.get(email=self.request.user.email)


class RemoveClientView(generics.DestroyAPIView):
    queryset = models.Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.queryset.get(email=self.request.user.email)

class ManageClientListView(generics.ListAPIView):
    """View for listing clients"""
    queryset = models.Client.objects.all()
    serializer_class = ClientSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

class ManageClientDetailView(generics.RetrieveAPIView):
    """View for retrieving a single client"""
    queryset = models.Client.objects.all()
    serializer_class = ClientSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]


class ManageProjectListView(generics.ListAPIView):
    """View for listing projects"""
    queryset = models.Project.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

class ManageProjectDetailView(generics.RetrieveAPIView):
    """View for retrieving a signle project"""
    queryset = models.Project.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]