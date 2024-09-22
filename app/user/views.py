import json
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
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Replace , Lower
from django.db import connection
import json
from django.core.serializers.json import DjangoJSONEncoder
from datetime import timedelta, datetime

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

from django.utils import timezone
from datetime import timedelta
import json
from django.db.models import Count

class ManageFreelancerView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated freelancer"""
    serializer_class = serializers.FreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated freelancer"""
        return models.Freelancer.objects.get(id=self.request.user.id)

    def update(self, request, *args, **kwargs):
        """Handle freelancer update and merge skills based on 'skill' and 'type'."""
        instance = self.get_object()  # Get the current freelancer instance

        # Extract the incoming data (assuming 'skills' is sent as part of the update request)
        new_skills_data = request.data.get('skills')

        if new_skills_data:
            try:
                # Parse the JSON string to manipulate skills
                new_skills_list = json.loads(new_skills_data)

                # Retrieve existing skills from the freelancer instance
                current_skills_list = json.loads(instance.skills) if instance.skills else []

                # Create a dictionary with a tuple of ('skill', 'type') as the key to facilitate merging
                current_skills_dict = {
                    (skill['skill'], skill['type']): skill for skill in current_skills_list
                }

                # Merge new skills into the existing ones
                for new_skill in new_skills_list:
                    skill_key = (new_skill.get('skill'), new_skill.get('type'))

                    if skill_key in current_skills_dict:
                        # Update existing skill with new data (merge fields if needed)
                        current_skills_dict[skill_key].update(new_skill)
                    else:
                        # Add new skill to the list, ensuring 'verified': False if not provided
                        if 'verified' not in new_skill:
                            new_skill['verified'] = False
                        current_skills_dict[skill_key] = new_skill

                # Convert the updated skills back to a list
                merged_skills_list = list(current_skills_dict.values())

                # Convert the list back to JSON string before saving it
                request.data['skills'] = json.dumps(merged_skills_list)
            except json.JSONDecodeError:
                return Response({'error': 'Invalid JSON format for skills'}, status=status.HTTP_400_BAD_REQUEST)

        # Perform the update
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Check the freelancer's skills to create an appointment if necessary
        skills_data = json.loads(instance.skills)

        both_practical_theoretical = request.data.get('both_practical_theoretical', False)
        category_unverified_skills = {}
        skills_by_category = {}

        for skill in skills_data:
            category = skill.get('category')
            skill_type = skill.get('type')
            is_verified = skill.get('verified', False)
            skill_name = skill.get('skill')

            if not is_verified:
                if category not in skills_by_category:
                    skills_by_category[category] = {}
                if skill_name not in skills_by_category[category]:
                    skills_by_category[category][skill_name] = {'theoretical': False, 'practical': False}

                skills_by_category[category][skill_name][skill_type] = True

        for category, skills in skills_by_category.items():
            for skill_name, skill_types in skills.items():
                if both_practical_theoretical:
                    if skill_types['theoretical'] and skill_types['practical']:
                        if category not in category_unverified_skills:
                            category_unverified_skills[category] = []
                        category_unverified_skills[category].append(skill_name)
                else:
                    if skill_types['theoretical'] or skill_types['practical']:
                        if category not in category_unverified_skills:
                            category_unverified_skills[category] = []
                        category_unverified_skills[category].append(skill_name)

        for category, unverified_skills in category_unverified_skills.items():
            if len(unverified_skills) >= 1:
                print("trying to get avaliable interviewers...")
                # Find interviewers with relevant expertise
                available_interviewers = self.get_available_interviewers(category)
                print("avaliable interviewers found",available_interviewers)

                if available_interviewers:
                    print("trying to get avaliable appointment dates...")
                    # Generate appointment date options for available interviewers
                    appointment_date_options = self.generate_appointment_date_options(available_interviewers)
                    print("avaliable appointment dates found",appointment_date_options)

                    # Create an appointment with date options
                    appointment = models.Appointment.objects.create(
                        freelancer=instance,
                        category=category,
                        skills_passed=unverified_skills,
                        appointment_date_options=json.dumps(appointment_date_options, cls=DjangoJSONEncoder)
                    )
                    appointment.save()
                    # Create a notification for the freelancer about the appointment
                    notification = models.Notification.objects.create(
                    user=instance,
                    type='appointment_date_choice',
                    title=f"Interview Appointment for {category}",
                    description=f"Congratulations , You've passed your skills tests and now you are in the final interview round. Please select an interview date from the options given",
                    data =appointment.appointment_date_options
                     )


        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_available_interviewers(self, category):
        """Get interviewers who match the category and have availability."""
        print("Trying to get interviewers for category:", category)
        
        # Normalize the category string
        expertise = models.Services.objects.filter(name__icontains=category).first()
        
        # Check if expertise was found
        if not expertise:
            return []  # Return an empty list if no matching expertise is found
        
        # Filter active interviewers
        interviewers = models.Interviewer.objects.filter(
            expertise=expertise,
            is_active=True,
            interviews_per_week__gt=0
        )

        available_interviewers = []
        today = timezone.now()
        start_of_week = today - timedelta(days=today.weekday())  # Start of the current week
        end_of_week = start_of_week + timedelta(days=6)  # End of the current week

        for interviewer in interviewers:
            # Count the number of interviews the interviewer has this week
            interviews_this_week = models.FreelancerInterview.objects.filter(
                interviewer=interviewer,
                appointment__appointment_date__range=(start_of_week, end_of_week),
                done=False
            ).count()

            # Count the number of interviews the interviewer has today
            interviews_today = models.FreelancerInterview.objects.filter(
                interviewer=interviewer,
                appointment__appointment_date__date=today.date(),
                done=False
            ).count()

            # Check if the current time exceeds the interviewer's end working hour
            if today.time() <= interviewer.working_hours_end:
                # Calculate available slots
                remaining_weekly_slots = interviewer.interviews_per_week - interviews_this_week
                remaining_daily_slots = interviewer.max_interviews_per_day - interviews_today
                
                # Store only those who have slots available
                if remaining_weekly_slots > 0 and remaining_daily_slots > 0:
                    available_interviewers.append({
                        'interviewer': interviewer,
                        'remaining_weekly_slots': remaining_weekly_slots,
                        'remaining_daily_slots': remaining_daily_slots
                    })

        # Sort interviewers based on remaining slots (you can customize this sorting logic)
        available_interviewers.sort(key=lambda x: (x['remaining_weekly_slots'], x['remaining_daily_slots']), reverse=True)

        # Return only the interviewer objects
        return [entry['interviewer'] for entry in available_interviewers]

    def generate_appointment_date_options(self, interviewers):
        """Generate a list of available appointment dates for a group of interviewers."""
        date_options = []
        today = timezone.now()
        day_counter = 0

        # Try to find 5 available appointment slots from the pool of interviewers
        while len(date_options) < 5:
            for interviewer in interviewers:
                # Get the interviewer's working hours
                working_hours_start = interviewer.working_hours_start
                working_hours_end = interviewer.working_hours_end

                # Calculate the start and end of the week for the current iteration
                start_of_week = today + timedelta(days=day_counter)
                end_of_week = start_of_week + timedelta(days=6)

                # Generate potential appointment slots within working hours for each day of the week
                for single_day in range(7):
                    current_day = start_of_week + timedelta(days=single_day)
                    
                    # Create datetime objects for the start and end of working hours
                    appointment_start = timezone.make_aware(datetime.combine(current_day.date(), working_hours_start))
                    appointment_end = timezone.make_aware(datetime.combine(current_day.date(), working_hours_end))

                    # Count existing interviews for this interviewer in the given week
                    interviews_this_week = models.FreelancerInterview.objects.filter(
                        interviewer=interviewer,
                        appointment__appointment_date__range=(start_of_week, end_of_week),
                        done=False
                    ).count()

                    # Count existing interviews for today
                    interviews_today = models.FreelancerInterview.objects.filter(
                        interviewer=interviewer,
                        appointment__appointment_date__date=current_day.date(),
                        done=False
                    ).count()

                    # If the interviewer has availability this week and today, check the appointment time
                    if (interviews_this_week < interviewer.interviews_per_week and
                        interviews_today < interviewer.max_interviews_per_day):
                        # Check if the appointment time falls within the working hours
                        if appointment_start < appointment_end:  # Valid working hours
                            date_options.append({
                                "date": appointment_start.strftime('%Y-%m-%d %H:%M')
                            })

                    # If we've generated 5 options, stop
                    if len(date_options) >= 5:
                        break

                # Move to the next week if not enough options were generated
                if len(date_options) >= 5:
                    break
            
            day_counter += 7

        return date_options





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