import uuid
from django.shortcuts import get_object_or_404
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
from rest_framework.decorators import api_view
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode , urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.utils.crypto import get_random_string
from rest_framework.decorators import action
from core import models
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class ResumeViewSet(viewsets.ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get('email', None)  # Get the email from the request data

        # Check if the email is already associated with a resume
        if Resume.objects.filter(email=email).exists():
            raise ValidationError({"email": "This email address is already used."})

        # Generate a verification token and save it
        verification_token = get_random_string(32)
        resume_data = request.data.copy()
        serializer = self.get_serializer(data=resume_data)
        serializer.is_valid(raise_exception=True)
        resume = serializer.save()
        resume.verification_token = verification_token
        resume.save()
        # Send the verification email
        send_verification_email(resume)

        return Response(
            {"message": "Verification email sent. Please verify your email to continue."},
            status=status.HTTP_201_CREATED,
        )

    # @action(detail=True, methods=['post'], url_path='verify-email')
    # def verify_email(self, request, pk=None):
    #     resume = self.get_object()
    #     token = request.data.get('token')

    #     if not token or resume.verification_token != token:
    #         return Response({"error": "Invalid or missing verification token."}, status=status.HTTP_400_BAD_REQUEST)

    #     # Mark the email as verified
    #     resume.email_verified = True
    #     resume.save()

    #     # Continue with screening and freelancer creation
    #     resume_text = extract_text_from_pdf(resume.resume_file.path)  # Extract text from the PDF resume
    #     applied_positions = resume.applied_positions.all()  # Get all applied positions (Services)
    #     positions_applied_for = [position.name for position in applied_positions]

    #     score_result = score_resume_with_chatgpt(resume_text, positions_applied_for)

    #     # Iterate through the score_result dictionary to create ScreeningResult for each position
    #     screening_results = []
    #     for position, result in score_result.items():
    #         score = result.get('score', 0)
    #         comment = result.get('comment', '')
    #         passed = score >= 50  # Assuming the passing score threshold is 50
    #         service = Services.objects.get(name__iexact=position)
    #         screening_result = ScreeningResult.objects.create(
    #             resume=resume,
    #             score=score,
    #             passed=passed,
    #             comments=comment,
    #             position=service
    #         )
    #         screening_results.append(screening_result)

    #     # If any position passes, create a freelancer
    #     freelancer = None
    #     if any(result['score'] >= 50 for result in score_result.values()):
    #         freelancer = create_freelancer_from_resume(resume, applied_positions)

    #     # Prepare response data
    #     screening_result_serializer = ScreeningResultSerializer(screening_results, many=True)
    #     response_data = {
    #         "message": "Email verified and screening completed.",
    #         "screening_results": screening_result_serializer.data,
    #     }
    #     if freelancer:
    #         response_data["freelancer_created"] = True
        # if (freelancer):
        #         # available_interviewers = get_available_interviewers("soft_skills")
        #         # print("avaliable interviewers found",available_interviewers)

        #         # if available_interviewers:
        #         #     print("trying to get avaliable appointment dates...")
        #         #     # Generate appointment date options for available interviewers
        #         #     appointment_date_options = generate_appointment_date_options(available_interviewers)
        #         #     print("avaliable appointment dates found",appointment_date_options)

        #         #     # Create an appointment with date options
        #         #     appointment = models.Appointment.objects.create(
        #         #         freelancer=freelancer,
        #         #         interview_type="soft_skills_assessment",
        #         #         appointment_date_options=json.dumps(appointment_date_options, cls=DjangoJSONEncoder)
        #         #     )
        #         #     appointment.save()
        #             # Create a notification for the freelancer about the appointment
        #             # notification = models.Notification.objects.create(
        #             # user=freelancer,
        #             # type='appointment_date_choice',
        #             # title=f"Interview Appointment for Soft Skills Assessment",
        #             # description=f"Congratulations, You've passed the resume assessment and passed to the first round Soft Skills Assessment !",
        #             # data={
        #             #     "appointment_id": str(appointment.id),  # Include appointment ID as a string
        #             #     "appointment_date_options": appointment.appointment_date_options  # Include the date options
        #             # }
        #             # Create a notification for the freelancer about the assessment result
        #             notification = models.Notification.objects.create(
        #             user=freelancer,
        #             type='alert',
        #             title=f"Soft Skills Assessment Passes",
        #             description=f"Congratulations, You've passed the resume assessment and passed to the first round Soft Skills Assessment !",
        #             )

        return Response(response_data, status=status.HTTP_200_OK)

# @action(detail=True, methods=['post'])
# def verify_email(self, request, pk=None):
#     resume = self.get_object()  # Get the resume by primary key (UUID)
#     token = request.data.get('token')  # Get the token from the request

#     if not token or resume.verification_token != token:
#         return Response({"error": "Invalid or missing verification token."}, status=status.HTTP_400_BAD_REQUEST)

#     # Mark the email as verified
#     resume.is_email_verified = True
#     resume.save()

#     # Continue with the screening process (your existing logic here)
#     resume_text = extract_text_from_pdf(resume.resume_file.path)
#     applied_positions = resume.applied_positions.all()
#     positions_applied_for = [position.name for position in applied_positions]

#     score_result = score_resume_with_chatgpt(resume_text, positions_applied_for)

#     screening_results = []
#     for position, result in score_result.items():
#         score = result.get('score', 0)
#         comment = result.get('comment', '')
#         passed = score >= 50
#         service = Services.objects.get(name__iexact=position)
#         screening_result = ScreeningResult.objects.create(
#             resume=resume,
#             score=score,
#             passed=passed,
#             comments=comment,
#             position=service
#         )
#         screening_results.append(screening_result)

#     freelancer = None
#     if any(result['score'] >= 50 for result in score_result.values()):
#         freelancer = create_freelancer_from_resume(resume, applied_positions)

#     screening_result_serializer = ScreeningResultSerializer(screening_results, many=True)
#     response_data = {
#         "message": "Email verified and screening completed.",
#         "screening_results": screening_result_serializer.data,
#     }
#     if freelancer:
#         response_data["freelancer_created"] = True

#     return Response(response_data, status=status.HTTP_200_OK)

from uuid import UUID


@api_view(['POST'])
def verify_email(request):
    print("Trying to find resume...")

    token = request.data.get('token')
    pk = request.data.get('pk')

    try:
        # Decode base64-encoded pk
        pk_decoded = urlsafe_base64_decode(pk).decode('utf-8')
        resume_id = UUID(pk_decoded)  # Convert to UUID to validate format
    except (ValueError, TypeError):
        raise ValidationError("Invalid or malformed UUID.")

    resume = get_object_or_404(Resume, pk=resume_id)

    if resume.verification_token != token:
        return Response({"error": "Invalid or missing verification token."}, status=status.HTTP_400_BAD_REQUEST)
    
    resume.is_email_verified = True
    resume.verification_token = ""
    resume.save()

    # Continue with the screening process (your existing logic here)
    resume_text = extract_text_from_pdf(resume.resume_file.path)
    applied_positions = resume.applied_positions.all()
    positions_applied_for = [position.name for position in applied_positions]

    score_result = score_resume_with_chatgpt(resume_text, positions_applied_for)

    screening_results = []
    for position, result in score_result.items():
        score = result.get('score', 0)
        comment = result.get('comment', '')
        passed = score >= 50
        service = Services.objects.get(name__iexact=position)
        screening_result = ScreeningResult.objects.create(
            resume=resume,
            score=score,
            passed=passed,
            comments=comment,
            position=service
        )
        screening_results.append(screening_result)

    freelancer = None
    if any(result['score'] >= 50 for result in score_result.values()):
        freelancer = create_freelancer_from_resume(resume, applied_positions)
        freelancer.email_verified = True
        freelancer.save()
    screening_result_serializer = ScreeningResultSerializer(screening_results, many=True)
    response_data = {
        "message": "Email verified and watch out your email for your application result.",
        "screening_results": screening_result_serializer.data,
    }
    if freelancer:
        response_data["freelancer_created"] = True

    return Response(response_data, status=status.HTTP_200_OK)

def send_email(to_email, subject, html_content):
    print("to email is ",to_email)
    print("subject is ",subject)
    print("html_content is ",html_content)
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )
    print("from email is",settings.DEFAULT_FROM_EMAIL)
    print("api key is ",settings.EMAIL_HOST_USER)
    print("message is ",message)
    try:
        sg = SendGridAPIClient(settings.EMAIL_HOST_USER)
        response = sg.send(message)
        print("email sent")
        return response.status_code
    except Exception as e:
        print("error sending email ",str(e))
        return str(e)

# def send_verification_email(resume):
#     print("resume email is ",resume.email)
#     print("verification token is ",verification_token)
#     uid = urlsafe_base64_encode(force_bytes(resume.pk))
#     verify_url = f"{settings.FRONTEND_URL}/verify-email/{uid}/{verification_token}/"
    
#     # Subject for the email
#     subject = "Verify your email address"
    
#     # HTML content for the email
#     html_content = f"""
#     <html>
#         <body>
#             <p>Click the link below to verify your email address:</p>
#             <a href="{verify_url}">{verify_url}</a>
#         </body>
#     </html>
#     """
    
#     # Call send_email function with the recipient email, subject, and HTML content
#     return send_email(resume.email, subject, html_content)

def send_verification_email(resume):
    token = resume.verification_token
    uid = urlsafe_base64_encode(str(resume.id).encode())
    verification_url = "resumes/{}/verify-email/{}/".format(uid, token)
    full_url = f"{settings.FRONTEND_URL}{verification_url}"
    # Subject for the email
    subject = "Verify your email address"
    
    # HTML content for the email
    html_content = f"""
    <html>
        <body>
            <p>Click the link below to verify your email address:</p>
            <a href="{full_url}">{full_url}</a>
        </body>
    </html>
    """
    
    # Call send_email function with the recipient email, subject, and HTML content
    return send_email(resume.email, subject, html_content)

# @api_view(['GET'])
# def verify_email(request, uidb64, token):
#     try:
#         uid = urlsafe_base64_encode(uidb64).decode()
#         resume = Resume.objects.get(pk=uid)
#     except (Resume.DoesNotExist, ValueError, TypeError):
#         return Response({"error": "Invalid verification link."}, status=400)

#     if default_token_generator.check_token(resume, token):
#         resume.is_email_verified = True
#         resume.save()
#         return Response({"message": "Email verified successfully."})
#     return Response({"error": "Verification link is invalid or expired."}, status=400)






def addFreelancerSkills(freelancer_id , selected_technologies):
     # Update freelancer's skills using selectedTechnologies
        freelancer = models.Freelancer.objects.get(id=freelancer_id)
        existing_skills = json.loads(freelancer.skills) if freelancer.skills else []

        # Iterate over services and technologies
        for service_id, technology_ids in selected_technologies.items():
            # Fetch the service name for the category
            service = models.Services.objects.get(id=service_id)
            category = service.name

            for tech_id in technology_ids:
                # Fetch the technology name for the skill
                technology = models.Technology.objects.get(id=tech_id)
                skill_name = technology.name

                # Add practical and theoretical skills for the technology
                new_skills = [
                    {
                        "category": category,
                        "skill": skill_name,
                        "type": "practical",
                        "both_practical_theoretical": True,
                        "verified": True
                    },
                    {
                        "category": category,
                        "skill": skill_name,
                        "type": "theoretical",
                        "both_practical_theoretical": True,
                        "verified": True
                    }
                ]
                existing_skills.extend(new_skills)

        # Save the updated skills to the freelancer object
        freelancer.skills = json.dumps(existing_skills)
        freelancer.save()


@api_view(['PATCH'])
def activate_full_assessment(request, freelancer_id):
    try:
        # Data passed in the request body with applied positions and corresponding statuses
        modal_data = request.data.get('modalData', None)  # or `modalData` key, depending on structure
        selected_technologies = request.data.get('selectedTechnologies', {})

        # Iterate over each applied position's ID and its corresponding assessment statuses
        for position_id, status_data in modal_data.items():
            try:
                # Fetch the FullAssessment object for the given position_id and freelancer_id
                full_assessment = models.FullAssessment.objects.get(
                    freelancer_id=freelancer_id,
                    applied_position_id=position_id
                )
                
                # Update the fields with the new statuses
                # full_assessment.soft_skills_assessment_status = status_data.get("soft_skills_assessment_status", full_assessment.soft_skills_assessment_status)
                full_assessment.depth_skill_assessment_status = status_data.get("depth_skill_assessment_status", full_assessment.depth_skill_assessment_status)
                full_assessment.live_assessment_status = status_data.get("live_assessment_status", full_assessment.live_assessment_status)
                
                # Set the status to 'pending'
                full_assessment.status = 'pending'
                user = models.Freelancer.objects.get(pk=freelancer_id)
                # Save the updated FullAssessment object
                full_assessment.save()
                notification = models.Notification.objects.create(
                user=user,
                type='alert',
                title="Full Assessment Activated",
                description="Full Assessment is now activated you can start taking the assessemtns!",
                )
                notification.save()
                 # HTML content for the email
                html_content = f"""
                <html>
                <body>
                <p>Congratualations , you have passed to the first round which is full assessment.</p>
                <p>You can start taking the assessments by login using account credentials used during applying.</p>
                </body>
                </html>
                """
                send_email(user.email,"Congratualtions you have passed to the first round!",html_content)

            except models.FullAssessment.DoesNotExist:
                return Response(
                    {"detail": f"FullAssessment object not found for position ID {position_id}."},
                    status=status.HTTP_404_NOT_FOUND
                )
        if (len(selected_technologies.items()) > 0):
                addFreelancerSkills(freelancer_id , selected_technologies)
        
        # After updating all assessments, return a success response
        # You may choose to return a summary or just a success message
        return Response({"detail": "Full assessments activated successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        # Catch any unexpected errors
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['PATCH'])
def approve_freelancer(request, freelancer_id):
    try:
        # Parse the data from the request
        modal_data = request.data.get('modalData', None)
        selected_technologies = request.data.get('selectedTechnologies', {})

        # Iterate over applied positions to update assessments
        for position_id, status_data in modal_data.items():
            try:
                # Fetch the FullAssessment object for the given position_id and freelancer_id
                full_assessment = models.FullAssessment.objects.get(
                    freelancer_id=freelancer_id,
                    applied_position_id=position_id
                )

                # Update assessment statuses
                full_assessment.soft_skills_assessment_status = "passed"
                full_assessment.depth_skill_assessment_status = "passed"
                full_assessment.live_assessment_status = "passed"
                full_assessment.status = "passed"
                full_assessment.finished = True
                full_assessment.save()
                user = models.Freelancer.objects.get(pk=freelancer_id)
                notification = models.Notification.objects.create(
                user=user,
                type='alert',
                title = "You're Approved!",
                description = "Congratulations! You are now a valued member of this exceptional community of freelancers. Welcome aboard!"  
                )
                notification.save()
                html_content = f"""
                <html>
                <body>
                <p>You are now a valued member of this exceptional community of freelancers. Welcome aboard!</p>
                </body>
                </html>
                """
                send_email(user.email,"You're Approved to join EthioGurus!",html_content)
            except models.FullAssessment.DoesNotExist:
                return Response(
                    {"detail": f"FullAssessment object not found for position ID {position_id}."},
                    status=status.HTTP_404_NOT_FOUND
                )
        if (len(selected_technologies.items()) > 0):
            addFreelancerSkills(freelancer_id , selected_technologies)
        return Response(
            {"detail": "Full assessments activated and freelancer skills updated successfully."},
            status=status.HTTP_200_OK
        )

    except models.Freelancer.DoesNotExist:
        return Response(
            {"detail": f"Freelancer with ID {freelancer_id} not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except models.Service.DoesNotExist as e:
        return Response(
            {"detail": f"Service not found: {str(e)}"},
            status=status.HTTP_404_NOT_FOUND
        )
    except models.Technology.DoesNotExist as e:
        return Response(
            {"detail": f"Technology not found: {str(e)}"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)





@api_view(['PATCH'])
def assign_soft_skills_assessment_appointment(request, freelancer_id):
    try:
        # Extract the applied_position_id from the request data
        modal_data = request.data.get('modalData', None)  # or `modalData` key, depending on structure
        applied_position_id = list(modal_data.keys())[0]  # Assuming position_id is the first key in the dictionary

        # Get the FullAssessment object for the freelancer and applied position
        full_assessment = models.FullAssessment.objects.get(
            freelancer_id=freelancer_id,
            applied_position_id=applied_position_id
        )

        # Update the soft_skills_assessment_status field to 'pending'
        full_assessment.soft_skills_assessment_status = 'pending'
        full_assessment.save()

        # Find available interviewers for the soft skills assessment
        available_interviewers = get_available_interviewers("soft_skills")
        print("Available interviewers found:", available_interviewers)

        if available_interviewers:
            print("Trying to get available appointment dates...")
            # Generate appointment date options
            appointment_date_options = generate_appointment_date_options(available_interviewers)
            print("Available appointment dates found:", appointment_date_options)

            # Create an appointment with the generated date options
            appointment = models.Appointment.objects.create(
                freelancer=full_assessment.freelancer,
                interview_type="soft_skills_assessment",
                appointment_date_options=json.dumps(appointment_date_options, cls=DjangoJSONEncoder)
            )
            appointment.save()

            # Create a notification for the freelancer about the appointment
            notification = models.Notification.objects.create(
                user=full_assessment.freelancer,
                type='alert',
                title="Soft Skills Assessment Appointment",
                description="Congratulations, You've passed the resume assessment and moved to the first round Soft Skills Assessment! Please select your appointment date.",
            )
            notification.save()

            # Return the updated FullAssessment object along with appointment details
            serializer = FullAssessmentSerializer(full_assessment)
            
            return Response({
                "assessment": serializer.data,
                "appointment": {
                    "id": appointment.id,
                    "appointment_date_options": appointment.appointment_date_options
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "detail": "No available interviewers for soft skills assessment."
            }, status=status.HTTP_400_BAD_REQUEST)

    except models.FullAssessment.DoesNotExist:
        return Response(
            {"detail": "FullAssessment object not found for this freelancer."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response({
            "detail": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
def assign_live_assessment_appointment(request, freelancer_id):
    try:
        # Extract the applied_position_id from the request data
        applied_position_id = request.data.get('applied_position_id', None)

        # Get the FullAssessment object for the freelancer and applied position
        full_assessment = models.FullAssessment.objects.get(
            freelancer_id=freelancer_id,
            applied_position_id=applied_position_id
        )

        # Update the soft_skills_assessment_status field to 'pending'
        full_assessment.live_assessment_status = 'pending'
        full_assessment.save()

        # Find available interviewers for the soft skills assessment
        available_interviewers = get_available_interviewers("live_interview")
        print("Available interviewers found:", available_interviewers)

        if available_interviewers:
            print("Trying to get available appointment dates...")
            # Generate appointment date options
            appointment_date_options = generate_appointment_date_options(available_interviewers)
            print("Available appointment dates found:", appointment_date_options)

            # Create an appointment with the generated date options
            appointment = models.Appointment.objects.create(
                freelancer=full_assessment.freelancer,
                interview_type="live_assessment",
                category = "live_assessment",
                appointment_date_options=json.dumps(appointment_date_options, cls=DjangoJSONEncoder)
            )
            appointment.save()

            # Create a notification for the freelancer about the appointment
            notification = models.Notification.objects.create(
                user=full_assessment.freelancer,
                type='alert',
                title="Live Assessment Appointment",
                description="Congratulations, You've passed the depth skill assessment and moved to the live Assessment! Please select your appointment date.",
            )
            notification.save()
            message="Congratulations, You've passed the depth skill assessment and moved to the live Assessment! Please select your appointment date by loggin in..",
            subject = 'Interview appointment Notification'
            message_ = f'Dear {full_assessment.freelancer.full_name},\n\n {message}".\n\nThank you for your continued efforts.'
            html_content = f"""
                <html>
                <body>
                <p>{message_}</p>
                </body>
                </html>
                """
            send_email(full_assessment.freelancer.email, subject, html_content)

            # Return the updated FullAssessment object along with appointment details
            serializer = FullAssessmentSerializer(full_assessment)
            
            return Response({
                "assessment": serializer.data,
                "appointment": {
                    "id": appointment.id,
                    "appointment_date_options": appointment.appointment_date_options
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "detail": "No available interviewers for live assessment."
            }, status=status.HTTP_400_BAD_REQUEST)

    except models.FullAssessment.DoesNotExist:
        return Response(
            {"detail": "FullAssessment object not found for this freelancer."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response({
            "detail": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)




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

    def update(self, request, *args, **kwargs):
        # Call the parent class's update method
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        message = ""
        if "depth_skill_assessment_status" in request.data:
            message = f"you have passed depth skill assessment for {instance.applied_position.name}."
        if "on_hold" in request.data:
            on_hold_duration = request.data.get("on_hold_duration")
            message = f"unfortunatelly you have failed the depth skill assessment for {instance.applied_position.name} and you will have to wait {on_hold_duration} to take the assessment again"
        self.send_assessment_update_email(instance , message)

        return Response(serializer.data)

    def send_assessment_update_email(self, assessment , message):
        """Send an email notification when the assessment status is updated."""
        subject = 'Assessment Update Notification'
        message_ = f'Dear {assessment.freelancer.full_name},\n\n {message}".\n\nThank you for your continued efforts.'
        html_content = f"""
                <html>
                <body>
                <p>{message_}</p>
                </body>
                </html>
                """
        send_email(assessment.freelancer.email,subject,html_content)        
        print("Email sent successfully.")


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
        try:
            # Retrieve the full assessment for the freelancer
            full_assessments = models.FullAssessment.objects.filter(freelancer=freelancer_id , status="pending")
        except models.FullAssessment.DoesNotExist:
            return Response({"error": "Full assessment not found for the given freelancer."}, status=status.HTTP_404_NOT_FOUND)

        # Filter FullAssessment records based on the provided IDs
        if not full_assessments.exists():
            return Response({"error": "No FullAssessment records found for the provided IDs."}, status=status.HTTP_404_NOT_FOUND)

        # Validate and update each FullAssessment record
        updated_assessments = []
        for assessment in full_assessments:
            serializer = FullAssessmentSerializer(assessment, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                updated_assessments.append(serializer.data)
            else:
                return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        message = ""
       
        if "on_hold" in request.data:
            on_hold_duration = request.data.get("on_hold_duration")
            message = f"unfortunatelly you have failed the live interview assessment and you will have to wait {on_hold_duration} to take the assessment again"
        elif "live_assessment_status" in request.data:
            message = f"you have passed live interview assessment."
        freelancer = models.Freelancer.objects.get(pk=freelancer_id)
        self.send_assessment_update_email(freelancer , message)
        return Response(updated_assessments, status=status.HTTP_200_OK)


def send_assessment_update_email(self, freelancer , message):
        """Send an email notification when the assessment status is updated."""
        subject = 'Assessment Update Notification'
        message_ = f'Dear {freelancer.full_name},\n\n {message}".\n\nThank you for your continued efforts.'
        html_content = f"""
                <html>
                <body>
                <p>{message_}</p>
                </body>
                </html>
                """
        send_email(freelancer.email,subject,html_content)        
        print("Email sent successfully.")


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


class NotStartedAssessmentsView(APIView):
    """
    API endpoint to fetch Resumes and ScreeningResults for assessments that have not started.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Query FullAssessment objects with not_started statuses
            full_assessments = models.FullAssessment.objects.filter(
                status='not_started',
            )

            # Get the freelancer emails from the filtered FullAssessments
            freelancer_emails = full_assessments.values_list('freelancer__email', flat=True).distinct()

            # Query Resumes that match the freelancer emails
            resumes = Resume.objects.filter(email__in=freelancer_emails)

            # Query ScreeningResults linked to the filtered Resumes
            screening_results = ScreeningResult.objects.filter(resume__in=resumes)

            # Serialize data
            resumes_serializer = ResumeSerializer(resumes, many=True)
            screening_results_serializer = ScreeningResultSerializer(screening_results, many=True)
            full_assessments_serializer = FullAssessmentSerializer(full_assessments , many=True)
            # Return response
            return Response(
                {
                    "resumes": resumes_serializer.data,
                    "screening_results": screening_results_serializer.data,
                    "full_assesments":full_assessments_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


