from rest_framework import serializers
from core import models


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for the Project model object"""
    
    class Meta:
        model = models.Project
        fields = ['id', 'client', 'title', 'description', 'budget', 'deadline', 'created_at', 'updated_at', 'status']
        read_only_fields = ['id','client', 'created_at', 'updated_at']  # These fields will be read-only
    def get_client_name(self, obj):
        # Assuming Client model has a field 'client_name'
        if obj.client:
            return obj.client.client_name  # Replace 'client_name' with the actual field name in your Client model
        return None