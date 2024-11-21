from rest_framework import viewsets, status
from rest_framework.response import Response
from .utils import extract_text_from_pdf, score_resume_with_chatgpt, send_resume_result_email, create_freelancer_from_resume
from core.models import Resume, ScreeningResult, ScreeningConfig , Field , Services
from .serializers import ResumeSerializer, ScreeningResultSerializer, ScreeningConfigSerializer , FieldSerializer , FullAssessmentSerializer
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, datetime
import json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission


from core import models
class ResumeViewSet(viewsets.ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer

    def create(self, request, *args, **kwargs):
        # Create the resume instance
        email = request.data.get('email', None)  # Get the email from the request data

        # Check if the email is already associated with a resume
        if Resume.objects.filter(email=email).exists():
            raise ValidationError({"email": "This email address is already used."})

        response = super().create(request, *args, **kwargs)
        resume = Resume.objects.get(pk=response.data['id'])  # Retrieve the created Resume object

        # Automatically screen the resume after creation
        resume_text = extract_text_from_pdf(resume.resume_file.path)  # Extract text from the PDF resume
        applied_positions = resume.applied_positions.all()  # Get all applied positions (Services)

        # Send all positions applied for to the scoring function
        positions_applied_for = [position.name for position in applied_positions]  # Assuming 'name' is the field you want to use

        score_result = score_resume_with_chatgpt(resume_text, positions_applied_for)  # Pass all positions to the scoring function

        # Iterate through the score_result dictionary to create ScreeningResult for each position
        screening_results = []
        for position, result in score_result.items():
            score = result.get('score', 0)
            comment = result.get('comment', '')
            passed = score >= 50  # Assuming the passing score threshold is 70
            service = Services.objects.get(name__iexact=position)
            screening_result = ScreeningResult.objects.create(
                resume=resume,
                score=score,
                passed=passed,
                comments=comment,
                position = service
            )
            screening_results.append(screening_result)

        # # Send email with the result of the screening for all positions
        # send_resume_result_email(resume.email, score_result)
        freelancer = None
        # If the resume passes the screening, create a freelancer from the resume
        if any(result['score'] >= 50 for result in score_result.values()):
            freelancer = create_freelancer_from_resume(resume , applied_positions)
        # Return the original response along with the screening results
        screening_result_serializer = ScreeningResultSerializer(screening_results, many=True)
        response.data['screening_results'] = screening_result_serializer.data
        if (freelancer):
                # available_interviewers = get_available_interviewers("soft_skills")
                # print("avaliable interviewers found",available_interviewers)

                # if available_interviewers:
                #     print("trying to get avaliable appointment dates...")
                #     # Generate appointment date options for available interviewers
                #     appointment_date_options = generate_appointment_date_options(available_interviewers)
                #     print("avaliable appointment dates found",appointment_date_options)

                #     # Create an appointment with date options
                #     appointment = models.Appointment.objects.create(
                #         freelancer=freelancer,
                #         interview_type="soft_skills_assessment",
                #         appointment_date_options=json.dumps(appointment_date_options, cls=DjangoJSONEncoder)
                #     )
                #     appointment.save()
                    # Create a notification for the freelancer about the appointment
                    # notification = models.Notification.objects.create(
                    # user=freelancer,
                    # type='appointment_date_choice',
                    # title=f"Interview Appointment for Soft Skills Assessment",
                    # description=f"Congratulations, You've passed the resume assessment and passed to the first round Soft Skills Assessment !",
                    # data={
                    #     "appointment_id": str(appointment.id),  # Include appointment ID as a string
                    #     "appointment_date_options": appointment.appointment_date_options  # Include the date options
                    # }
                    # Create a notification for the freelancer about the assessment result
                    notification = models.Notification.objects.create(
                    user=freelancer,
                    type='alert',
                    title=f"Soft Skills Assessment Passes",
                    description=f"Congratulations, You've passed the resume assessment and passed to the first round Soft Skills Assessment !",
                    )
        return response

class ScreeningResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScreeningResult.objects.all()
    serializer_class = ScreeningResultSerializer

class ScreeningConfigViewSet(viewsets.ModelViewSet):
    queryset = ScreeningConfig.objects.all()
    serializer_class = ScreeningConfigSerializer

class FieldViewSet(viewsets.ModelViewSet):
    queryset = Field.objects.all()
    serializer_class = FieldSerializer

class FullAssessmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing FullAssessment objects.
    Provides list, retrieve, create, update, and delete actions.
    """
    queryset = models.FullAssessment.objects.all()
    serializer_class = FullAssessmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optionally filter by the current user's freelancer ID
        if self.request.user.is_authenticated and hasattr(self.request.user, 'freelancer'):
            return models.FullAssessment.objects.filter(freelancer=self.request.user.freelancer)
        return models.FullAssessment.objects.none()


class FreelancerFullAssessmentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, freelancer_id, format=None):
        try:
            full_assessment = models.FullAssessment.objects.get(freelancer=freelancer_id)
        except models.FullAssessment.DoesNotExist:
            return Response({"error": "Full assessment not found for the given freelancer."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = FullAssessmentSerializer(full_assessment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FullAssessmentUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def patch(self, request, freelancer_id, format=None):
        user = self.request.user
        # user_interviewer = getattr(user, 'interviewer', None)
        try:
            # Retrieve the full assessment for the freelancer
            full_assessment = models.FullAssessment.objects.get(freelancer=freelancer_id)
        except models.FullAssessment.DoesNotExist:
            return Response({"error": "Full assessment not found for the given freelancer."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the authenticated user is an interviewer
        # if not user_interviewer:
        #     return Response({"error": "You do not have permission to update this assessment."}, status=status.HTTP_403_FORBIDDEN)

        # Serialize the data for update using the existing FullAssessmentSerializer
        serializer = FullAssessmentSerializer(full_assessment, data=request.data, partial=True)

        if serializer.is_valid():
            # Save the updated data
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



def get_available_interviewers(type):
        """Get interviewers for soft skills and have availability."""
                        
        # Filter active interviewers
        interviewers = models.Interviewer.objects.filter(
            is_active=True,
            interviews_per_week__gt=0,
            type=type
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

            remaining_weekly_slots = interviewer.interviews_per_week - interviews_this_week
            remaining_daily_slots = interviewer.max_interviews_per_day - interviews_today
            available_interviewers.append({
                    'interviewer': interviewer,
                    'remaining_weekly_slots': remaining_weekly_slots,
                    'remaining_daily_slots': remaining_daily_slots,
                })

        # Sort interviewers based on remaining slots (you can customize this sorting logic)
        available_interviewers.sort(key=lambda x: (x['remaining_weekly_slots'], x['remaining_daily_slots'],), reverse=True)

        # Return only the interviewer objects
        return [entry['interviewer'] for entry in available_interviewers]

def generate_appointment_date_options(interviewers):
        """Generate a list of available appointment dates for a group of interviewers."""
        date_options = []
        today = timezone.now()
        day_counter = 0

        # Try to find 5 available appointment slots from the pool of interviewers
        for interviewer in interviewers:
            # Get the interviewer's working hours
            working_hours_start = interviewer.working_hours_start
            working_hours_end = interviewer.working_hours_end

            # Calculate the start and end of the week for the current iteration
            start_of_week = today + timedelta(days=day_counter)
            end_of_week = start_of_week + timedelta(days=6)

            # Generate potential appointment slots within working hours for each day of the week
            for single_day in range(7):
                print("day",single_day)
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
                    print("passed check")
                    if appointment_start < appointment_end:  # Valid working hours
                        date_options.append({
                            "interviewer_id":interviewer.id,
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
