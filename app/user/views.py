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
from django.contrib.auth import authenticate
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from .serializers import MessageCountSerializer, NotificationCountSerializer


def get_tokens_for_user(user):
    """Generate JWT tokens for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class LoginView(APIView):
    """
    View to handle user login.
    Returns a JWT token, email, and role of the user.
    """

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(request, email=email, password=password)
        print("user is ",user)
        if user is not None:
            # Generate tokens using SimpleJWT
            refresh = RefreshToken.for_user(user)
            token = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }

            # Determine user role (Freelancer or Client)
            role = None
            if models.Freelancer.objects.filter(id=user.id).exists():
                role = 'freelancer'
            elif models.Client.objects.filter(id=user.id).exists():
                role = 'client'
            
            # Prepare response data
            data = {
                'token': token,
                'email': user.email,
                'role': role,
            }

            return Response(data, status=status.HTTP_200_OK)

        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class UserRoleView(APIView):
    """
    View to return the user's role based on their JWT token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Extract the user role from the request.user object
        print("in role get")
        user = request.user
        print("user is ",user)
        if models.Freelancer.objects.filter(id=user.id).exists():
            role = 'freelancer'
        elif models.Client.objects.filter(id=user.id).exists():
            role = 'client'
        else:
            role = 'Admin'
        return Response({'role': role}, status=status.HTTP_200_OK)



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

class TokenRefreshView(APIView):
    """
    View to handle refreshing JWT tokens.
    Accepts a refresh token and returns a new access and refresh token.
    """
    
    def post(self, request):
        refresh_token = request.data.get('refresh')

        if refresh_token is None:
            return Response({'detail': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = refresh.access_token

            # Optionally, rotate the refresh token
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

            return Response({
                'access': str(new_access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)
        
        except TokenError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AuthenticateView(APIView):
    """
    View to check if the access token is valid and not expired.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'detail': 'Authorization header is required'}, status=status.HTTP_400_BAD_REQUEST)

        access_token = auth_header.split(' ')[1]

        try:
            # Validate the access token
            token = AccessToken(access_token)
            # Optionally, you can also check for additional claims in the token if needed

            return Response({'detail': 'Access token is valid'}, status=status.HTTP_200_OK)
        
        except TokenError as e:
            return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_message_count(request):
    user = request.user

    # Determine if the user is a client or freelancer
    if hasattr(user, 'client'):
        chats = user.client.chats.all()
    elif hasattr(user, 'freelancer'):
        chats = user.freelancer.chats.all()
    else:
        return Response({'detail': 'User not associated with a client or freelancer profile.'}, status=status.HTTP_400_BAD_REQUEST)

    unread_count = models.Message.objects.filter(chat__in=chats, read=False).count()
    
    # Serialize the response
    data = {'count': unread_count}
    serializer = MessageCountSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_notification_count(request):
    user = request.user
    
    unread_count = models.Notification.objects.filter(user=user, read=False).count()
    
    # Serialize the response
    data = {'count': unread_count}
    serializer = NotificationCountSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


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

class NotificationViewSet(viewsets.ModelViewSet):
    """Viewset for managing notifications"""
    serializer_class = serializers.NotificationSerializer
    queryset = models.Notification.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter notifications to only include those for the authenticated user"""
        user = self.request.user
        return self.queryset.filter(user=user)

class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = serializers.PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password has been updated successfully.'}, status=status.HTTP_200_OK)