from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from core import models


class FreelancerSerializer(serializers.ModelSerializer):
    """Serializer for the Freelancer model object"""
    
    class Meta:
        model = models.Freelancer
        fields = ['id','email', 'password', 'first_name', 'last_name' ,'bio','skills','portfolio','experience','certifications','phone_number','social_links','hourly_rate','availability_status',
                  'preferred_working_hours','preferred_communication_channels','average_rating','reviews','languages_spoken','selected_payment_method','verified','address','account_status','profile_picture']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}
        read_only_fields =['id']
    def create(self, validated_data):
        """Create and return a freelancer with encrypted password"""
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Update and return a freelancer"""
        password = validated_data.pop('password', None)
        freelancer = super().update(instance, validated_data)

        if password:
            freelancer.set_password(password)
            freelancer.save()

        return freelancer


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for the Client model object"""
    
    class Meta:
        model = models.Client
        fields = ['id','email', 'password', 'company_name' ,'projects_posted','average_project_budget','verified','reviews','address','account_status','profile_picture']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}
        read_only_fields =['id']
    def create(self, validated_data):
        """Create and return a client with encrypted password"""
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Update and return a client"""
        password = validated_data.pop('password', None)
        client = super().update(instance, validated_data)

        if password:
            client.set_password(password)
            client.save()

        return client


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer for obtaining JWT tokens"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({'email': self.user.email})
        return data
