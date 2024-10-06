from rest_framework.permissions import IsAuthenticated
from core.models import Appointment, FreelancerInterview, Interviewer
from .serializers import AppointmentSerializer, FreelancerInterviewSerializer, InterviewerSerializer , AppointmentDateSelectionSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import viewsets, generics, status 
from core import models
class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    """Viewset for managing appointments."""
    serializer_class = AppointmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Check if the user is a Freelancer
        if models.Freelancer.objects.filter(id=user.id).exists():
            return Appointment.objects.filter(freelancer=user).order_by('-appointment_date')

        # Check if the user is an Interviewer
        elif Interviewer.objects.filter(id=user.id).exists():
            # Get freelancers associated with the interviewer via FreelancerInterview
            freelancers = FreelancerInterview.objects.filter(interviewer=user).values_list('freelancer', flat=True)
            return Appointment.objects.filter(freelancer__in=freelancers).order_by('-appointment_date')

        # If user is neither Freelancer nor Interviewer, return empty queryset
        return Appointment.objects.none()



class FreelancerInterviewViewSet(viewsets.ModelViewSet):
    queryset = FreelancerInterview.objects.all()
    serializer_class = FreelancerInterviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        # Retrieve the interview instance being updated
        instance = self.get_object()
        
        if not models.Interviewer.objects.filter(id= request.user.id).exists():
            raise PermissionDenied("You do not have permission to update the interview.")
        # Only the interviewer can update the `passed` and `feedback` fields.
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        # Validate the data
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def perform_update(self, serializer):
        # Save the update, only the interviewer can set `passed` and `feedback`
        serializer.save()

# ViewSet for Interviewer
class InterviewerViewSet(viewsets.ModelViewSet):
    queryset = Interviewer.objects.all()
    serializer_class = InterviewerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Check if the user is a Freelancer
        if models.Freelancer.objects.filter(id=user.id).exists():
            return models.FreelancerInterview.objects.filter(freelancer=user)

        # Check if the user is an Interviewer
        elif Interviewer.objects.filter(id=user.id).exists():
            return models.FreelancerInterview.objects.filter(interviewer=user)

        # If user is neither Freelancer nor Interviewer, return empty queryset
        return Interviewer.objects.none()


class SelectAppointmentDateView(generics.UpdateAPIView):
    """API view for selecting an appointment date from available options"""
    serializer_class = AppointmentDateSelectionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Retrieve the appointment instance"""
        # Get the freelancer's appointment based on the request data (e.g., appointment ID)
        appointment_id = self.kwargs.get('pk')
        return Appointment.objects.get(id=appointment_id, freelancer=self.request.user)

    def perform_update(self, serializer):
        """Update the appointment with the selected date"""
        appointment = self.get_object()
        selected_date = serializer.validated_data['selected_date']

        # Update the appointment with the selected date
        appointment.appointment_date = selected_date
        appointment.appointment_date_options = []  # Clear the date options after selection
        appointment.save()

        return Response({'message': 'Appointment date selected successfully'}, status=status.HTTP_200_OK)

class UpdateAppointmentStatusView(generics.UpdateAPIView):
    """API view for updating the appointment status"""
    serializer_class = AppointmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]  # Ensure only interviewers can access

    def get_object(self):
        """Retrieve the appointment instance"""
        appointment_id = self.kwargs.get('pk')
        return generics.get_object_or_404(Appointment, id=appointment_id)

    def update(self, request, *args, **kwargs):
        """Override the update method to set 'done' to True"""
        if not models.Interviewer.objects.filter(id= request.user.id).exists():
            raise PermissionDenied("You do not have permission to update the interview.")
        appointment = self.get_object()
      
        # Update the appointment with the selected date
        appointment.done = True
        appointment.save()
        return Response({'message': 'Appointment status updated successfully'}, status=status.HTTP_200_OK)




class InterviewerDashboardViewSet(viewsets.ViewSet):
    """Viewset for Interviewer Dashboard displaying latest appointments and interviews."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Get the latest appointments for the interviewer
        appointments = Appointment.objects.filter(freelancer__in=FreelancerInterview.objects.filter(interviewer=request.user).values_list('freelancer', flat=True)).order_by('-appointment_date')[:5]
        interviews = FreelancerInterview.objects.filter(interviewer=request.user).order_by('-id')[:5]  # Get the latest 5 interviews
        
        appointment_serializer = AppointmentSerializer(appointments, many=True)
        interview_serializer = FreelancerInterviewSerializer(interviews, many=True)

        return Response({
            'latest_appointments': appointment_serializer.data,
            'latest_interviews': interview_serializer.data,
        })
    