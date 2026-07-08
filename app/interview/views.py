import logging

from rest_framework.permissions import IsAuthenticated
from core.models import Appointment, FreelancerInterview, Interviewer

logger = logging.getLogger(__name__)
from .serializers import AppointmentSerializer, FreelancerInterviewSerializer, InterviewerSerializer , AppointmentDateSelectionSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import viewsets, generics, status 
from core import models
from core import models
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


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



def send_email(to_email, subject, html_content):
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return 200
    except Exception as e:
        logger.error("error sending email: %s", str(e))
        return str(e)

class FreelancerInterviewViewSet(viewsets.ModelViewSet):
    serializer_class = FreelancerInterviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if Interviewer.objects.filter(id=user.id).exists():
            return FreelancerInterview.objects.filter(interviewer=user)
        if models.Freelancer.objects.filter(id=user.id).exists():
            return FreelancerInterview.objects.filter(freelancer=user)
        return FreelancerInterview.objects.none()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if not Interviewer.objects.filter(id=request.user.id).exists():
            raise PermissionDenied("You do not have permission to update the interview.")

        if instance.interviewer_id != request.user.id:
            raise PermissionDenied("You are not the assigned interviewer for this interview.")
        # Only the interviewer can update the `passed` and `feedback` fields.
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        # Validate the data
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        notification_description = ""
        result =""
        if instance.passed:
            notification_description = f"Congratulations you have passed the interview round for {instance.appointment.category} !"
            result = f"Result: Passed"
        else:
            notification_description = f"Unfortunately you have not passed the interview round for {instance.appointment.category}! Keep working on your skills and try again!"
            result = f"Result: Failed"
        models.Notification.objects.create(
                    user=instance.freelancer,
                    type='alert',
                    title=f"Interview for {instance.appointment.category} Finished ",
                    description=notification_description
            )

        models.Notification.objects.create(
                    user=instance.interviewer,
                    type='alert',
                    title=f"Interview for {instance.appointment.category} with {instance.freelancer.full_name} Finished ",
                    description=result
            )
        subject = "Interview result update!"
    
        # HTML content for the email
        html_content = f"""
        <html>
            <body>
                <p>{notification_description}</p>
            </body>
        </html>
        """
        
        # Call send_email function with the recipient email, subject, and HTML content
        send_email(instance.freelancer.email, subject, html_content)


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
    """API view for selecting an appointment date from available options."""
    serializer_class = AppointmentDateSelectionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        appointment_id = self.kwargs.get('pk')
        return generics.get_object_or_404(
            Appointment, id=appointment_id, freelancer=self.request.user
        )

    def update(self, request, *args, **kwargs):
        appointment = self.get_object()
        serializer = AppointmentDateSelectionSerializer(
            data=request.data,
            context={'appointment': appointment},
        )
        serializer.is_valid(raise_exception=True)
        appointment.appointment_date = serializer.validated_data['selected_date']
        appointment.appointment_date_options = []
        appointment.save()
        return Response({'message': 'Appointment date selected successfully'}, status=status.HTTP_200_OK)

class UpdateAppointmentStatusView(generics.UpdateAPIView):
    """API view for updating the appointment status — restricted to the assigned interviewer."""
    serializer_class = AppointmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        if not Interviewer.objects.filter(id=self.request.user.id).exists():
            raise PermissionDenied("You do not have permission to update appointments.")
        appointment_id = self.kwargs.get('pk')
        assigned_freelancers = FreelancerInterview.objects.filter(
            interviewer=self.request.user
        ).values_list('freelancer_id', flat=True)
        return generics.get_object_or_404(
            Appointment, id=appointment_id, freelancer_id__in=assigned_freelancers
        )

    def update(self, request, *args, **kwargs):
        appointment = self.get_object()
        appointment.done = True
        appointment.save()
        return Response({'message': 'Appointment status updated successfully'}, status=status.HTTP_200_OK)




class InterviewerDashboardViewSet(viewsets.ViewSet):
    """
    Viewset for Interviewer Dashboard displaying latest appointments and interviews.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Fetch the latest 5 interviews related to the interviewer
        interviews = FreelancerInterview.objects.filter(
            interviewer=request.user
        ).order_by('-id')[:5]

        # Extract the related appointment IDs from these interviews
        appointment_ids = interviews.values_list('appointment_id', flat=True)

        # Fetch the corresponding appointments
        appointments = Appointment.objects.filter(
            id__in=appointment_ids
        ).order_by('-appointment_date')

        # Serialize the data
        interview_serializer = FreelancerInterviewSerializer(interviews, many=True)
        appointment_serializer = AppointmentSerializer(appointments, many=True)

        return Response({
            'latest_interviews': interview_serializer.data,
            'latest_appointments': appointment_serializer.data,
        })


class InterviewerAppointments(viewsets.ViewSet):
    """Viewset for Interviewer Dashboard displaying latest appointments and interviews."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
       # Fetch the latest 5 interviews related to the interviewer
        interviews = FreelancerInterview.objects.filter(
            interviewer=request.user
        )

        # Extract the related appointment IDs from these interviews
        appointment_ids = interviews.values_list('appointment_id', flat=True)

        # Fetch the corresponding appointments
        appointments = Appointment.objects.filter(
            id__in=appointment_ids
        ).order_by('-appointment_date')

        # Serialize the data
        appointment_serializer = AppointmentSerializer(appointments, many=True)

        return Response({
            'appointments': appointment_serializer.data,
        })
class Interivews(viewsets.ViewSet):
    """Viewset for Interviewer Dashboard displaying latest interviews."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Get the latest appointments for the interviewer
        interviews = FreelancerInterview.objects.filter(interviewer=request.user).order_by('-id')
        
        interview_serializer = FreelancerInterviewSerializer(interviews, many=True)

        return Response({
            'interviews': interview_serializer.data,
        })