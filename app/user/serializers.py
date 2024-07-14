'''
serializers for the user api
'''
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core import models
from rest_framework_simplejwt.tokens import RefreshToken


class FreelancerSerializer(serializers.ModelSerializer):
    """serializer for the model object"""
    token = serializers.SerializerMethodField()

    class Meta:
        model = models.Freelancer
        fields = ['email', 'password', 'first_name', 'last_name', 'token']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}

    def create(self, validated_data):
        """create and return a freelancer with encrypted password"""
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Update and return a freelancer."""
        password = validated_data.pop('password', None)
        freelancer = super().update(instance, validated_data)

        if password:
            freelancer.set_password(password)
            freelancer.save()

        return freelancer

    def get_token(self, obj):
        refresh = RefreshToken.for_user(obj)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

class ClientSerializer(serializers.ModelSerializer):
    """serializer for the model object"""
    token = serializers.SerializerMethodField()

    class Meta:
        model = models.Client
        fields = ['email', 'password', 'company_name', 'token']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}

    def create(self, validated_data):
        """create and return a client with encrypted password"""
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Update and return a client."""
        password = validated_data.pop('password', None)
        client = super().update(instance, validated_data)

        if password:
            client.set_password(password)
            client.save()

        return client

    def get_token(self, obj):
        refresh = RefreshToken.for_user(obj)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer for obtaining JWT tokens"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({'email': self.user.email})
        return data