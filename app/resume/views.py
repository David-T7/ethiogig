import uuid
import jwt
from datetime import timedelta, datetime
import json

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.crypto import get_random_string
from django.db.models import Count, Q, F
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.hashers import make_password
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core import models
from core.models import Resume, ScreeningResult, ScreeningConfig, Field, Services, AssessmentTermination, FullAssessment
from . import serializers
from .utils import extract_text_from_pdf, score_resume_with_gemini, send_resume_result_email, create_freelancer_from_resume

from uuid import UUID

class ResumeViewSet(viewsets.ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = serializers.ResumeSerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get('email')
        is_email_verified = request.data.get('is_email_verified', None)
        services = request.data.getlist('applied_positions', [])  # Multiple services
        password = request.data.get('password')

        if not services:
            return Response({"error": "At least one service must be selected."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch valid service objects
        valid_services = Services.objects.filter(id__in=services)
        if not valid_services:
            return Response({"error": "Selected services do not exist."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if there are any applications on hold for this email and the applied positions
        on_hold_positions = models.ApplicationOnHold.objects.filter(email=email, position__in=valid_services).values_list("position__name", flat=True)
        
        if on_hold_positions:
            return Response(
                {"error": "Your application is currently on hold for the following positions:", "positions": list(on_hold_positions)},
                status=status.HTTP_400_BAD_REQUEST
            )

        resumes = []
        verification_token = get_random_string(32)  # One token for all resumes
        hashed_password = make_password(password)  # Hash password once

        for service in valid_services:
            resume_data = request.data.copy()
            resume_data["applied_position"] = service.id
            resume_data["verification_token"] = verification_token
            resume_data["password"] = hashed_password  # Assign hashed password

            serializer = self.get_serializer(data=resume_data)
            serializer.is_valid(raise_exception=True)
            resume = serializer.save()
            resumes.append(resume)

        if resumes:
            send_verification_email(resumes[0])

        return Response(
            {
                "message": "Application was successful. Please verify your email to continue.",
                "resume_ids": [str(r.id) for r in resumes],
            },
            status=status.HTTP_201_CREATED,
        )

AI_SCREENING_PASS_THRESHOLD = 60

PIPELINE_STAGES = [
    'ai_screening',
    'kyc',
    'theoretical_test',
    'practical_test',
    'resume_check',
    'full_assessment',
]


def pipeline_past_stage(resume, stage):
    """True if this stage or any later pipeline stage is already passed."""
    try:
        idx = PIPELINE_STAGES.index(stage)
    except ValueError:
        return False
    return models.VettingPipelineRecord.objects.filter(
        resume=resume,
        stage__in=PIPELINE_STAGES[idx:],
        status='passed',
    ).exists()


def _invite_pipeline_stage(resume, stage, initial_status='invited'):
    """
    Create or activate a pipeline stage without downgrading completed progress.
    Returns True when the candidate should receive a new invitation for this stage.
    """
    if pipeline_past_stage(resume, stage):
        return False

    record = models.VettingPipelineRecord.objects.filter(resume=resume, stage=stage).first()
    if record:
        if record.status == 'pending':
            record.status = initial_status
            record.save(update_fields=['status', 'updated_at'])
            return True
        return False

    models.VettingPipelineRecord.objects.create(
        resume=resume,
        stage=stage,
        status=initial_status,
    )
    return True


def generate_candidate_token(resume):
    payload = {
        'user_id': str(resume.id),
        'email': resume.email,
        'full_name': resume.full_name,
        'role': 'candidate',
        'exp': datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def send_resume_for_screening(resume):
    resume_text = extract_text_from_pdf(resume.resume_file.path)
    applied_position = resume.applied_position
    score_result = score_resume_with_gemini(resume_text, applied_position.name)

    screening_results = []
    passed_any = False

    if not score_result or 'error' in score_result:
        print(f"Gemini scoring failed for {resume.email}: {score_result}")
        return screening_results

    for position, result in score_result.items():
        if not isinstance(result, dict):
            continue

        score = result.get('score', 0)
        comment = result.get('comment', '')
        passed = score >= AI_SCREENING_PASS_THRESHOLD

        if passed:
            passed_any = True
        else:
            hold_days = 120 if score < 20 else 60 if score < 40 else 30
            hold_until = timezone.now() + timedelta(days=hold_days)
            models.ApplicationOnHold.objects.create(
                resume=resume,
                email=resume.email,
                position=applied_position,
                hold_until=hold_until,
                reason=f"AI resume screening failed. Score: {score}. Comments: {comment}",
            )

        ScreeningResult.objects.create(
            resume=resume,
            score=score,
            passed=passed,
            comments=comment,
            position=applied_position,
        )
        screening_results.append(score)

    if passed_any:
        models.VettingPipelineRecord.objects.update_or_create(
            resume=resume,
            stage='ai_screening',
            defaults={'status': 'passed', 'score': max(screening_results)},
        )
        if not pipeline_past_stage(resume, 'kyc'):
            trigger_kyc_stage(resume)

    return screening_results


def trigger_kyc_stage(resume):
    if not _invite_pipeline_stage(resume, 'kyc', 'invited'):
        return
    token = generate_candidate_token(resume)
    kyc_url = (
        f"{settings.FRONTEND_URL}verify-account"
        f"?token={token}&candidate_id={resume.id}"
    )
    html_content = f"""
    <html><body>
    <p>Congratulations! Your resume passed our AI screening for <strong>{resume.applied_position.name}</strong>.</p>
    <p>The next step is identity verification. Please complete KYC before the skills tests.</p>
    <p><a href="{kyc_url}">Complete Identity Verification</a></p>
    <p>This link expires in 7 days. Do not share it.</p>
    </body></html>
    """
    send_email(resume.email, "Next Step: Identity Verification", html_content)


def trigger_theoretical_test(resume):
    if not _invite_pipeline_stage(resume, 'theoretical_test', 'invited'):
        return
    token = generate_candidate_token(resume)
    from urllib.parse import quote
    test_url = (
        f"{settings.FRONTEND_URL}skills-test/theoretical"
        f"?token={token}&candidate_id={resume.id}"
        f"&position={quote(resume.applied_position.name)}"
    )
    html_content = f"""
    <html><body>
    <p>Your identity has been verified. The next step is the theoretical skills assessment.</p>
    <p>Position: <strong>{resume.applied_position.name}</strong></p>
    <p>This is a timed test. Ensure you are in a quiet environment with camera access before starting.</p>
    <p><a href="{test_url}">Start Theoretical Skills Test</a></p>
    <p>This link expires in 7 days.</p>
    </body></html>
    """
    send_email(resume.email, "Next Step: Theoretical Skills Test", html_content)


def trigger_practical_test(resume):
    if not _invite_pipeline_stage(resume, 'practical_test', 'invited'):
        return
    token = generate_candidate_token(resume)
    from urllib.parse import quote
    test_url = (
        f"{settings.FRONTEND_URL}skills-test/practical"
        f"?token={token}&candidate_id={resume.id}"
        f"&position={quote(resume.applied_position.name)}"
    )
    html_content = f"""
    <html><body>
    <p>You passed the theoretical skills test. The next step is the practical coding assessment.</p>
    <p>Position: <strong>{resume.applied_position.name}</strong></p>
    <p>This is a hands-on coding challenge. Camera proctoring is active during the test.</p>
    <p><a href="{test_url}">Start Practical Skills Test</a></p>
    <p>This link expires in 7 days.</p>
    </body></html>
    """
    send_email(resume.email, "Next Step: Practical Skills Test", html_content)


def trigger_resume_check_stage(resume):
    if not _invite_pipeline_stage(resume, 'resume_check', 'pending'):
        return
    current_time = timezone.now().time()
    today = timezone.now().date()

    checker_qs = models.ResumeChecker.objects.annotate(
        checks_today=Count(
            'resume_checks',
            filter=Q(resume_checks__created_at__date=today),
        ),
        checks_this_week=Count(
            'resume_checks',
            filter=Q(resume_checks__created_at__gte=timezone.now() - timedelta(days=7)),
        ),
    ).filter(
        checks_today__lt=F('max_resume_check_per_day'),
        checks_this_week__lt=F('resume_check_per_week'),
    )

    available_checker = (
        checker_qs.filter(
            working_hours_start__lte=current_time,
            working_hours_end__gte=current_time,
        ).first()
        or checker_qs.first()
    )

    if available_checker:
        models.ResumeCheck.objects.get_or_create(
            resumechecker=available_checker,
            resume=resume,
        )

    html_content = f"""
    <html><body>
    <p>You have passed the automated skills assessments for <strong>{resume.applied_position.name}</strong>.</p>
    <p>Your application is now being reviewed by our team. We will contact you with the next steps shortly.</p>
    </body></html>
    """
    send_email(resume.email, "Application Under Review", html_content)


def advance_pipeline(resume, completed_stage):
    try:
        idx = PIPELINE_STAGES.index(completed_stage)
    except ValueError:
        return

    if idx + 1 >= len(PIPELINE_STAGES):
        return

    next_stage = PIPELINE_STAGES[idx + 1]
    if next_stage == 'kyc':
        trigger_kyc_stage(resume)
    elif next_stage == 'theoretical_test':
        trigger_theoretical_test(resume)
    elif next_stage == 'practical_test':
        trigger_practical_test(resume)
    elif next_stage == 'resume_check':
        trigger_resume_check_stage(resume)


def _hold_days_for_score(score):
    if score is None:
        return 30
    if score < 20:
        return 120
    if score < 40:
        return 60
    return 30


def handle_stage_failure(resume, stage, score):
    hold_days = _hold_days_for_score(score)
    hold_until = timezone.now() + timedelta(days=hold_days)
    models.ApplicationOnHold.objects.create(
        resume=resume,
        email=resume.email,
        position=resume.applied_position,
        hold_until=hold_until,
        reason=f"Did not meet the threshold for stage '{stage}'. Score: {score}.",
    )
    html_content = f"""
    <html><body>
    <p>Thank you for completing the {stage.replace('_', ' ')} stage.</p>
    <p>Unfortunately you did not meet the required threshold at this time.</p>
    <p>You may reapply after <strong>{hold_until.strftime('%B %d, %Y')}</strong>.</p>
    </body></html>
    """
    send_email(resume.email, "Application Update", html_content)


def _authenticate_candidate(request, resume_id):
    """
    Validates the candidate Bearer token and confirms it belongs to resume_id.
    Returns (payload, None) on success or (None, error_response) on failure.
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, Response(
            {'error': 'Authentication required. Provide a Bearer token.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token = auth.split(' ', 1)[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None, Response({'error': 'Token has expired.'}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return None, Response({'error': 'Invalid token.'}, status=status.HTTP_401_UNAUTHORIZED)

    if payload.get('role') != 'candidate':
        return None, Response({'error': 'Not a candidate token.'}, status=status.HTTP_403_FORBIDDEN)
    if str(payload.get('user_id')) != str(resume_id):
        return None, Response({'error': 'Token does not match this resume.'}, status=status.HTTP_403_FORBIDDEN)

    return payload, None


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_candidate_token(request, resume_id):
    """
    Issues a 7-day JWT for microservice access.
    Requires the candidate's password in the request body.
    """
    try:
        resume = models.Resume.objects.get(id=resume_id, is_email_verified=True)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found or email not verified.'}, status=status.HTTP_404_NOT_FOUND)

    password = request.data.get('password')
    if not password:
        return Response({'error': "'password' is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not resume.check_password(password):
        return Response({'error': 'Incorrect password.'}, status=status.HTTP_401_UNAUTHORIZED)

    token = generate_candidate_token(resume)
    return Response({
        'token': token,
        'candidate_id': str(resume.id),
        'expires_in': 7 * 24 * 3600,
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def report_stage_result(request, resume_id):
    """
    Records the result of a pipeline stage and advances the pipeline.
    Body: { stage, passed, score (optional), submission_id (optional), notes (optional) }
    Requires the candidate Bearer token issued by get_candidate_token.
    """
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    stage = request.data.get('stage')
    passed = request.data.get('passed')
    score = request.data.get('score')
    submission_id = request.data.get('submission_id')
    notes = request.data.get('notes', '')

    if stage not in PIPELINE_STAGES:
        return Response({'error': f"Unknown stage '{stage}'."}, status=status.HTTP_400_BAD_REQUEST)
    if passed is None:
        return Response({'error': "'passed' is required."}, status=status.HTTP_400_BAD_REQUEST)

    record, _ = models.VettingPipelineRecord.objects.get_or_create(
        resume=resume,
        stage=stage,
    )
    record.status = 'passed' if passed else 'failed'
    record.score = score
    record.notes = notes
    if submission_id:
        try:
            record.external_submission_id = uuid.UUID(str(submission_id))
        except (ValueError, AttributeError):
            pass
    record.save()

    if passed:
        advance_pipeline(resume, stage)
    else:
        handle_stage_failure(resume, stage, score)

    next_stage = PIPELINE_STAGES[PIPELINE_STAGES.index(stage) + 1] if PIPELINE_STAGES.index(stage) + 1 < len(PIPELINE_STAGES) else None
    return Response({
        'recorded': stage,
        'status': record.status,
        'next_stage': next_stage if passed else None,
    })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_pipeline_status(request, resume_id):
    """Returns the pipeline status for a resume. Requires the candidate Bearer token."""
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    records = models.VettingPipelineRecord.objects.filter(resume=resume).order_by('created_at')
    serializer = serializers.VettingPipelineRecordSerializer(records, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_candidate_info(request, resume_id):
    """Returns basic candidate profile fields for KYC forms. Requires candidate Bearer token."""
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'candidate_id': str(resume.id),
        'full_name': resume.full_name,
        'email': resume.email,
        'position': resume.applied_position.name if resume.applied_position else None,
    })


@api_view(['POST'])
def verify_email(request):
    print("Trying to find resumes...")

    token = request.data.get('token')
    pk = request.data.get('pk')

    try:
        # Decode base64-encoded pk
        pk_decoded = urlsafe_base64_decode(pk).decode('utf-8')
        resume_id = UUID(pk_decoded)  # Convert to UUID to validate format
    except (ValueError, TypeError):
        raise ValidationError("Invalid or malformed UUID.")

    # Retrieve the main resume object
    main_resume = get_object_or_404(Resume, pk=resume_id)

    if main_resume.verification_token != token:
        return Response({"error": "Invalid or missing verification token."}, status=status.HTTP_400_BAD_REQUEST)

    # Find all resumes with the same email
    all_resumes = Resume.objects.filter(email=main_resume.email, is_email_verified=False)

    screening_results = []
    for resume in all_resumes:
        resume.is_email_verified = True
        resume.verification_token = ""
        resume.save()
        send_resume_for_screening(resume)
    screening_result_serializer = serializers.ScreeningResultSerializer(screening_results, many=True)

    response_data = {
        "message": "Email verified. Watch out for your application results.",
        "screening_results": screening_result_serializer.data,
    }

    return Response(response_data, status=status.HTTP_200_OK)




def send_email(recipient_email, subject, html_content):
    text_content = "Please view this email in an HTML-compatible email client."

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )

    email_message.attach_alternative(html_content, "text/html")
    email_message.send(fail_silently=False)

    return True

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

    verification_url = f"resumes/{uid}/verify-email/{token}/"
    full_url = f"{settings.FRONTEND_URL}{verification_url}"

    subject = "Verify your email address"

    text_content = f"""
Hello,

Click the link below to verify your email address:

{full_url}
"""

    html_content = f"""
    <html>
        <body>
            <p>Click the link below to verify your email address:</p>
            <p>
                <a href="{full_url}">Verify Email</a>
            </p>
        </body>
    </html>
    """

    return send_email(
        recipient_email=resume.email,
        subject=subject,
        html_content=html_content
    )

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
def activate_full_assessment(request, resume_id):
    try:
        # Data passed in the request body with applied positions and corresponding statuses
        modal_data = request.data.get('modalData', None)  # or `modalData` key, depending on structure
        selected_technologies = request.data.get('selectedTechnologies', {})
        resume = models.Resume.objects.get(id=resume_id)
        resume_check = models.ResumeCheck.objects.get(resume=resume)
        freelancer = create_freelancer_from_resume(resume)
        # Iterate over each applied position's ID and its corresponding assessment statuses
        for position_id, status_data in modal_data.items():
            try:
                # Fetch the FullAssessment object for the given position_id and freelancer_id
                full_assessment = models.FullAssessment.objects.get(
                    freelancer_id=freelancer.id,
                    applied_position_id=position_id
                )
                
                # Update the fields with the new statuses
                # full_assessment.soft_skills_assessment_status = status_data.get("soft_skills_assessment_status", full_assessment.soft_skills_assessment_status)
                full_assessment.depth_skill_assessment_status = status_data.get("depth_skill_assessment_status", full_assessment.depth_skill_assessment_status)
                full_assessment.live_assessment_status = status_data.get("live_assessment_status", full_assessment.live_assessment_status)
                
                # Set the status to 'pending'
                full_assessment.status = 'pending'
                user = models.Freelancer.objects.get(pk=freelancer.id)
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
                 <p class="header">Congratulations, {user.first_name}!</p>
                <p>We are pleased to inform you that you have successfully advanced to the next stage of our selection process: the Full Assessment.</p>
                <p>You can now proceed with the assessments by logging in using the credentials you provided during your application.</p>
                <p>If you have any questions, feel free to reach out to us.</p>
                <p>Best regards,</p>
                <p><strong>The Recruitment Team</strong></p>
                <a href="https://yourwebsite.com/login" class="button">Start Assessment</a>
                </html>
                """
                send_email(user.email,"Congratualtions you have passed to the first round!",html_content)
                resume_check.done = True
                resume_check.save()
            except models.FullAssessment.DoesNotExist:
                return Response(
                    {"detail": f"FullAssessment object not found for position ID {position_id}."},
                    status=status.HTTP_404_NOT_FOUND
                )
        if (len(selected_technologies.items()) > 0):
                addFreelancerSkills(freelancer.id , selected_technologies)
        
        # After updating all assessments, return a success response
        # You may choose to return a summary or just a success message
        return Response({"detail": "Full assessments activated successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        # Catch any unexpected errors
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['PATCH'])
def approve_freelancer(request, resume_id):
    try:
        # Parse the data from the request
        modal_data = request.data.get('modalData', None)
        selected_technologies = request.data.get('selectedTechnologies', {})
        resume = models.Resume.objects.get(id=resume_id)
        freelancer = create_freelancer_from_resume(resume_id,resume.applied_positions.all())
        # Iterate over applied positions to update assessments
        for position_id, status_data in modal_data.items():
            try:
                # Fetch the FullAssessment object for the given position_id and freelancer_id
                full_assessment = models.FullAssessment.objects.get(
                    freelancer_id=freelancer.id,
                    applied_position_id=position_id
                )

                # Update assessment statuses
                full_assessment.soft_skills_assessment_status = "passed"
                full_assessment.depth_skill_assessment_status = "passed"
                full_assessment.live_assessment_status = "passed"
                full_assessment.status = "passed"
                full_assessment.finished = True
                full_assessment.save()
                user = models.Freelancer.objects.get(pk=freelancer.id)
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
                resume_check = models.ResumeCheck.objects.get(resume=resume)
                resume_check.done = True
                resume_check.save()
            except models.FullAssessment.DoesNotExist:
                return Response(
                    {"detail": f"FullAssessment object not found for position ID {position_id}."},
                    status=status.HTTP_404_NOT_FOUND
                )
        if (len(selected_technologies.items()) > 0):
            addFreelancerSkills(freelancer.id , selected_technologies)
        return Response(
            {"detail": "Full assessments activated and freelancer skills updated successfully."},
            status=status.HTTP_200_OK
        )

    except models.Freelancer.DoesNotExist:
        return Response(
            {"detail": f"Freelancer with ID {freelancer.id} not found."},
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
            serializer = serializers.FullAssessmentSerializer(full_assessment)
            
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
            html_content = f"""
                <html>
                <body>
                <p>{message}</p>
                </body>
                </html>
                """
            send_email(full_assessment.freelancer.email, subject, html_content)

            # Return the updated FullAssessment object along with appointment details
            serializer = serializers.FullAssessmentSerializer(full_assessment)
            
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
    serializer_class = serializers.ScreeningResultSerializer

class ScreeningConfigViewSet(viewsets.ModelViewSet):
    queryset = ScreeningConfig.objects.all()
    serializer_class = serializers.ScreeningConfigSerializer

class FieldViewSet(viewsets.ModelViewSet):
    queryset = Field.objects.all()
    serializer_class = serializers.FieldSerializer

class FullAssessmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing FullAssessment objects.
    Provides list, retrieve, create, update, and delete actions.
    """
    queryset = models.FullAssessment.objects.all()
    serializer_class = serializers.FullAssessmentSerializer
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
        
        serializer = serializers.FullAssessmentSerializer(full_assessment)
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
            serializer = serializers.FullAssessmentSerializer(assessment, data=request.data, partial=True)
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
        send_assessment_update_email(freelancer , message)
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
    API endpoint to fetch Resumes and ScreeningResults for assessments assigned to the authenticated ResumeChecker.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Ensure user is a ResumeChecker
            if not hasattr(request.user, "resumechecker"):
                raise PermissionDenied("Only ResumeCheckers can access this resource.")

            resume_checker = request.user.resumechecker  # Get the authenticated ResumeChecker

            # Get Resumes assigned to this ResumeChecker (not started yet)
            assigned_resume_checks = models.ResumeCheck.objects.filter(
                resumechecker=resume_checker, done=False  # Not completed yet
            )

            # Get list of assigned Resumes
            assigned_resumes = Resume.objects.filter(id__in=assigned_resume_checks.values_list('resume_id', flat=True))

            # Filter FullAssessments that match these resumes and are "not_started"
            full_assessments = FullAssessment.objects.filter(
                status='not_started',
                freelancer__email__in=assigned_resumes.values_list("email", flat=True)
            )

            # Get ScreeningResults linked to assigned Resumes
            screening_results = ScreeningResult.objects.filter(resume__in=assigned_resumes)

            # Serialize data
            resumes_serializer = serializers.ResumeSerializer(assigned_resumes, many=True)
            screening_results_serializer = serializers.ScreeningResultSerializer(screening_results, many=True)
            full_assessments_serializer = serializers.FullAssessmentSerializer(full_assessments, many=True)

            return Response(
                {
                    "resumes": resumes_serializer.data,
                    "screening_results": screening_results_serializer.data,
                    "full_assessments": full_assessments_serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






class AssessmentTerminationView(RetrieveUpdateAPIView):
    """
    API View to get or update a freelancer's assessment termination count.
    If the termination count reaches 3, all active assessments will be put on hold until a set date.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.AssessmentTerminationSerializer

    def get_object(self):
        freelancer_id = self.request.query_params.get("freelancer_id")
        if not freelancer_id:
            return None

        return AssessmentTermination.objects.filter(freelancer_id=freelancer_id).first()

    def patch(self, request, *args, **kwargs):
        freelancer_id = request.data.get("freelancer_id")
        if not freelancer_id:
            return Response({"error": "Freelancer ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        assessment_termination, created = AssessmentTermination.objects.get_or_create(
            freelancer_id=freelancer_id
        )

        # Increment termination count
        assessment_termination.termination_count += 1
        assessment_termination.save()

        # Check if termination count reaches 3
        if assessment_termination.termination_count >= 3:
            hold_duration = timedelta(days=120)  # Hold for 120 days
            hold_expiry = now() + hold_duration  # Calculate exact hold expiration date

            FullAssessment.objects.filter(
                freelancer_id=freelancer_id,
                finished=False,  # Only apply to active assessments
                on_hold=False  # Ensure we don't reapply hold
            ).update(
                status="on_hold",
                on_hold=True,
                hold_until=hold_expiry,  # Store exact expiry date
                updated_at=now()
            )

        serializer = self.get_serializer(assessment_termination)
        return Response(serializer.data, status=status.HTTP_200_OK)



class ApplicationOnHoldViewSet(viewsets.ModelViewSet):
    queryset = models.ApplicationOnHold.objects.all()
    serializer_class = serializers.ApplicationOnHoldSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]


    def perform_create(self, serializer):
        """Override to handle additional logic during creation."""
        application_on_hold = serializer.save()

        # Extract necessary details
        email = application_on_hold.email
        position = application_on_hold.position
        hold_until = application_on_hold.hold_until
        rejection_reason = getattr(application_on_hold, "rejection_reason", None)  # Ensure field exists

        # Format hold_until date as "July 20, 2023"
        hold_until_date = hold_until.strftime("%B %d, %Y") if hold_until else "a later date"

        # Construct email content dynamically
        email_subject = "Application Not Accepted"
        email_content = (
            f"Dear Applicant,\n\n"
            f"Your application for the position '{position}' has not been accepted.\n"
        )

        if rejection_reason:  # Add reason only if provided
            email_content += f"Reason: {rejection_reason}\n"

        email_content += f"You may reapply after {hold_until_date}.\n\nBest regards,\nRecruitment Team"

        # Send email notification
        send_email(email, email_subject, email_content)

        
