# serializers.py

from rest_framework import serializers
from core.models import Service, Technology

class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

class ServiceSerializer(serializers.ModelSerializer):
    technologies = TechnologySerializer(many=True, read_only=True)
    technology_ids = serializers.PrimaryKeyRelatedField(
        many=True, write_only=True, queryset=Technology.objects.all(), source='technologies')

    class Meta:
        model = Service
        fields = ['id', 'name', 'description', 'price', 'technologies', 'technology_ids', 'created_at', 'updated_at']
        read_only_fields = ['id','created_at','updated_at']
