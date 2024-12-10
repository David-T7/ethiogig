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
            'client',
            'title',
            'terms',
            'start_date',
            'end_date',
            'amount_agreed', 
            'duration',
            'freelancer_accepted_terms',
            'status',
            'hourly',
            'payment_status',
            'contract_update',
            'created_at',
            'milestone_based',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at','payment_status']
        
        def create(self, validated_data):
            freelancer_id = validated_data.pop('freelancer_id')
            freelancer = models.Freelancer.objects.get(pk=freelancer_id)
            contract = models.Contract.objects.create(freelancer=freelancer, **validated_data)
            return contract


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Milestone
        fields = ['id', 'contract', 'title', 'description', 'amount', 'due_date', 'is_completed','milestone_update','created_at', 'updated_at' , 'status']
        read_only_fields = ['id', 'created_at', 'updated_at']



class ContractFreelancerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Contract
        fields = [
            'id',
            'freelancer_accepted_terms',
        ]
        read_only_fields = ['id',]
        

    def create(self, validated_data):
        supporting_documents_data = self.context.get('request').FILES.getlist('supporting_documents')
        dispute = models.Dispute.objects.create(**validated_data)
        for document_data in supporting_documents_data:
            models.SupportingDocument.objects.create(file=document_data)
        return dispute


class CounterOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CounterOffer
        fields = [
            'id','proposed_amount','contract','title','sender','hourly','duration','milestone_based','status','start_date','end_date'
        ]
        read_only_fields = ['id',]


class CounterOfferMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CounterOfferMilestone
        fields = [
            'id','counter_offer','title', 'description', 'amount', 'due_date',
        ]
        read_only_fields = ['id',]

class SupportingDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SupportingDocument
        fields = ('id', 'file', 'uploaded_at', 'dispute','uploaded_by')
        read_only_fields = ('uploaded_at',)


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Dispute
        fields = (
            'id',
            'title',
            'description',
            'return_type',
            'return_amount',
            'contract',
            'status',
            'created_at',
            'created_by',
            'milestone',
            'updated_at',
            'response_deadline',
            'supporting_documents',
            'got_response'
        )
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'response_deadline',
        ]

class DisputeResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DisputeResponse
        fields = (
            'id',
            'title',
            'description',
            'return_type',
            'return_amount',
            'dispute',
            'response',
            'created_at',
            'created_by',
            'updated_at',
            'response_deadline',
            'supporting_documents',
            'got_response'
        )
        read_only_fields = [
            'id',
            'status',
            'created_at',
            'updated_at',
            'response_deadline',
        ]

class DRCFowrwardSerializer(serializers.ModelSerializer):
     class Meta:
        model = models.DrcForwardedDisputes
        fields = (
        'id',
        'dispute', 
        'dispute_manager',
        'solved', 
        'created_at', 
        'updated_at'
        )
        read_only_fields = [ 
        'id',
        'created_at',
        'updated_at'
        ]


class DrcResolvedDisputesSerializer(serializers.ModelSerializer):
     class Meta:
        model = models.DrcResolvedDisputes
        fields = (
        'id',
        'drc_forwarded', 
        'return_type',
        'return_amount',
        'title',
        'comment',
        'created_at', 
        'winner'
        )
        read_only_fields = [ 
        'id',
        'created_at',
        ]



class EscrowSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Escrow
        fields = [
            'id',
            'contract',
            'milestone',
            'amount',
            'status',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class DepositConfirmedUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Escrow
        fields = ['deposit_confirmed']

class FreelancerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Freelancer
        fields = ['id', 'full_name', 'professional_title', 'bio', 'skills', 'experience', 'hourly_rate','profile_picture']
        read_only_fields = ['id']