# views.py
from rest_framework import viewsets
from core.models import Service, Technology
from services import serializers
class TechnologyViewSet(viewsets.ModelViewSet):
    queryset = Technology.objects.all()
    serializer_class = serializers.TechnologySerializer

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = serializers.ServiceSerializer
