from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from core import models
from django.contrib.auth import get_user_model
User = get_user_model()

class FreelancerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Freelancer with fewer required fields"""
    
    class Meta:
        model = models.Freelancer
        fields = ['email', 'password', 'full_name']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}

    def create(self, validated_data):
        """Create and return a freelancer with encrypted password"""
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

class FreelancerSerializer(serializers.ModelSerializer):
    """Serializer for the Freelancer model object with all fields"""
    
    class Meta:
        model = models.Freelancer
        fields = ['id', 'email', 'password', 'full_name', 'bio', 'skills', 'prev_work_experience', 'experience','portfolio',
                  'certifications', 'phone_number', 'hourly_rate', 'availability_status',
                  'preferred_working_hours', 'average_rating', 'reviews',
                  'languages_spoken', 'selected_payment_method', 'verified', 'address', 'account_status',
                  'profile_picture']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}
        read_only_fields = ['id']

    def update(self, instance, validated_data):
        """Update and return a freelancer"""
        password = validated_data.pop('password', None)
        freelancer = super().update(instance, validated_data)

        if password:
            freelancer.set_password(password)
            freelancer.save()

        return freelancer


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for the Client model object with all fields"""
    
    class Meta:
        model = models.Client
        fields = ['id', 'email', 'password', 'company_name','contact_person','phone_number','projects_posted', 'average_rating',
                  'verified', 'reviews', 'address','selected_payment_method', 'account_status', 'profile_picture']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}
        read_only_fields = ['id']

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
    
class ClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a Client with minimal fields"""
    
    class Meta:
        model = models.Client
        fields = ['email', 'password', 'company_name','contact_person','phone_number']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}

    def create(self, validated_data):
        """Create and return a client with encrypted password"""
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance



class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer for obtaining JWT tokens"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({'email': self.user.email})
        return data

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Message
        fields = ['id', 'chat', 'sender', 'content', 'timestamp','read']
        read_only_fields = ['id', 'timestamp']

class ChatSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    class Meta:
        model = models.Chat
        fields = ['id', 'client', 'freelancer', 'created_at', 'messages']
        read_only_fields = ['id', 'created_at', 'messages']

class MessageCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()

class NotificationCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notification
        fields = ['id', 'user', 'type', 'title', 'description', 'timestamp', 'read','data']
        read_only_fields = ['id']

class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("New password must be at least 8 characters long.")
        return value

    def save(self):
        user = self.context['request'].user
        old_password = self.validated_data['old_password']
        new_password = self.validated_data['new_password']
        
        if not user.check_password(old_password):
            raise serializers.ValidationError("Old password is incorrect.")
        
        user.set_password(new_password)
        user.save()
        return user
