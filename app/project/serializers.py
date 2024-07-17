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
class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Contract
        fields = [
            'id',
            'project',
            'freelancer',
            'terms',
            'start_date',
            'end_date',
            'amount_agreed', 
            'freelancer_accepted_terms',
            'status',
            'payment_status',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        
        def create(self, validated_data):
            freelancer_id = validated_data.pop('freelancer_id')
            freelancer = models.Freelancer.objects.get(pk=freelancer_id)
            contract = models.Contract.objects.create(freelancer=freelancer, **validated_data)
            return contract
class ContractFreelancerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Contract
        fields = [
            'id',
            'freelancer_accepted_terms',
        ]
        read_only_fields = ['id',]
        
