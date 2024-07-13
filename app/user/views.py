from django.shortcuts import render
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from rest_framework import generics, authentication, permissions
from user.serializers import FreelancerSerializer , ClientSerializer
# Create your views here.

class CreateFreelancerView(generics.CreateAPIView):
    """create a new freelancer in the system"""
    serializer_class = FreelancerSerializer

class CreateClientView(generics.CreateAPIView):
    """create a new client in the system"""
    serializer_class = ClientSerializer