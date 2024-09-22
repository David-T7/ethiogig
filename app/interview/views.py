from rest_framework.permissions import IsAuthenticated
from core.models import Appointment, FreelancerInterview, Interviewer
from .serializers import AppointmentSerializer, FreelancerInterviewSerializer, InterviewerSerializer , AppointmentDateSelectionSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import viewsets, generics, status

# ViewSet for Appointment
class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        # If you want to filter appointments based on the logged-in user (freelancer)
        return Appointment.objects.filter(freelancer=self.request.user)

class FreelancerInterviewViewSet(viewsets.ModelViewSet):
    queryset = FreelancerInterview.objects.all()
    serializer_class = FreelancerInterviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        # Retrieve the interview instance being updated
        instance = self.get_object()
        
        # Check if the logged-in user is the interviewer for this interview
        if instance.interviewer != request.user:
            raise PermissionDenied("You are not allowed to update this interview.")

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
        # Optional: You can customize this queryset based on the logged-in user's permissions or roles
        return super().get_queryset()


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
