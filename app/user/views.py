from django.shortcuts import render
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from rest_framework import generics, authentication, permissions , status ,mixins
from user.serializers import FreelancerSerializer , ClientSerializer , CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response


from core import models
# Create your views here.

class CreateFreelancerView(generics.CreateAPIView):
    """create a new freelancer in the system"""
    serializer_class = FreelancerSerializer

class CreateClientView(generics.CreateAPIView):
    """create a new client in the system"""
    serializer_class = ClientSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    """Obtain JWT token pair"""
    serializer_class = CustomTokenObtainPairSerializer

class ManageFreelancerView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated freelancer."""
    serializer_class = FreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated freelancer user."""
        return models.Freelancer.objects.get(email =self.request.user.email)

class ManageClientView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated client."""
    serializer_class = ClientSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated client user."""
        return models.Client.objects.get(email =self.request.user.email)

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
