from django.shortcuts import render
from rest_framework import generics, authentication, permissions, status , viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from user import serializers
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from core import models
from project.serializers import ProjectSerializer
from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode
from django.shortcuts import get_object_or_404
from .utils import send_password_reset_email

def get_tokens_for_user(user):
    """Generate JWT tokens for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class FreelancerViewSet(viewsets.ModelViewSet):
    queryset = models.Freelancer.objects.all()
    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.FreelancerCreateSerializer
        return serializers.FreelancerSerializer
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        tokens = get_tokens_for_user(serializer.instance)
        return Response({**serializer.data, **tokens}, status=status.HTTP_201_CREATED, headers=headers)

class ClientViewSet(viewsets.ModelViewSet):
    """Create a new client in the system"""
    queryset = models.Client.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.ClientCreateSerializer
        return serializers.ClientSerializer
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        tokens = get_tokens_for_user(serializer.instance)
        return Response({**serializer.data, **tokens}, status=status.HTTP_201_CREATED, headers=headers)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Obtain JWT token pair"""
    serializer_class = serializers.CustomTokenObtainPairSerializer


class ManageFreelancerView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated freelancer"""
    serializer_class = serializers.FreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated freelancer"""
        return models.Freelancer.objects.get(id=self.request.user.id)


class ManageClientView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated client"""
    serializer_class = serializers.ClientSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated client"""
        return models.Client.objects.get(id=self.request.user.id)


class RemoveFreelancerView(generics.DestroyAPIView):
    """Remove the authenticated freelnacer"""
    queryset = models.Freelancer.objects.all()
    serializer_class = serializers.FreelancerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.queryset.get(id=self.request.user.id)


class RemoveClientView(generics.DestroyAPIView):
    """Remove the authenticated client"""
    queryset = models.Client.objects.all()
    serializer_class = serializers.ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.queryset.get(id=self.request.user.id)

class ManageClientListView(generics.ListAPIView):
    """View for listing clients"""
    queryset = models.Client.objects.all()
    serializer_class = serializers.ClientSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

class ManageFreelnacerListView(generics.ListAPIView):
    """View for listing freelancer"""
    queryset = models.Freelancer.objects.all()
    serializer_class = serializers.FreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]



# class ManageClientDetailView(generics.RetrieveAPIView):
#     """View for retrieving a single client"""
#     queryset = models.Client.objects.all()
#     serializer_class = serializers.ClientSerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [permissions.IsAuthenticated]

# class ManageFreelancerDetailView(generics.RetrieveAPIView):
#     """View for retrieving a single freelancer"""
#     queryset = models.Freelancer.objects.all()
#     serializer_class = serializers.FreelancerSerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [permissions.IsAuthenticated]



class ManageProjectListView(generics.ListAPIView):
    """View for listing all projects in the system"""
    queryset = models.Project.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

class ManageProjectDetailView(generics.RetrieveAPIView):
    """View for retrieving a single project"""
    queryset = models.Project.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]



class ChatViewSet(viewsets.ModelViewSet):
    """View for managing chats between client and freelancer"""
    queryset = models.Chat.objects.all()
    serializer_class = serializers.ChatSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter chats to only include those involving the authenticated user"""
        user = self.request.user
        if hasattr(user, 'client'):
            return self.queryset.filter(client=user.client)
        elif hasattr(user, 'freelancer'):
            return self.queryset.filter(freelancer=user.freelancer)
        else:
            return self.queryset.none()

class MessageViewSet(viewsets.ModelViewSet):
    """View for managing messages in a chat"""
    queryset = models.Message.objects.all()
    serializer_class = serializers.MessageSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Create a message in a chat"""
        chat_id = self.kwargs.get('chat_pk')
        chat = generics.get_object_or_404(models.Chat, pk=chat_id)
        serializer.save(chat=chat, sender=self.request.user)
    
@api_view(['POST'])
def reset_password(request, uidb64, token):
    """Reset the user's password."""
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_object_or_404(get_user_model(), pk=uid)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        # Handle password reset form submission
        password = request.data.get('new_password')
        if password:
            user.set_password(password)
            user.save()
            return Response({'message': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)
        return Response({'error': 'New password is required.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({'error': 'Invalid token or user ID.'}, status=status.HTTP_400_BAD_REQUEST)




class PasswordResetRequestView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = serializers.PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = models.User.objects.get(email=email)
                send_password_reset_email(email)
                return Response({'message': 'Password reset link sent'}, status=status.HTTP_200_OK)
            except models.User.DoesNotExist:
                return Response({'error': 'User with this email does not exist'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)