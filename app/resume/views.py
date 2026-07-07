import uuid
import jwt
from datetime import timedelta, datetime
import json

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction
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
from .vetting_catalog import MIN_TECHNOLOGIES_TO_PASS
from . import vetting_taxonomy_service as taxonomy
from .hold_policy import application_holds_enabled, active_application_hold
from .testing_policy import (
    skip_kyc_for_testing,
    skip_ai_screening_for_testing,
    skip_email_verification_for_testing,
    serialize_testing_policy,
)

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
        on_hold_positions = []
        if application_holds_enabled():
            on_hold_positions = models.ApplicationOnHold.objects.filter(
                email=email,
                position__in=valid_services,
                hold_until__gt=timezone.now(),
            ).values_list('position__name', flat=True)

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
            if skip_email_verification_for_testing():
                _auto_verify_email_for_testing(resumes)
            else:
                send_verification_email(resumes[0])

        return Response(
            {
                "message": (
                    "Application was successful. You can sign in to track your progress."
                    if skip_email_verification_for_testing()
                    else "Application was successful. Please verify your email to continue."
                ),
                "resume_ids": [str(r.id) for r in resumes],
                "email_verification_required": not skip_email_verification_for_testing(),
                "testing_policy": serialize_testing_policy(),
            },
            status=status.HTTP_201_CREATED,
        )

AI_SCREENING_PASS_THRESHOLD = 60

PIPELINE_STAGES = [
    'ai_screening',
    'kyc',
    'theoretical_test',
    'interview',
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


def generate_candidate_action_token(resume_id, purpose):
    jti = uuid.uuid4()
    models.CandidateActionToken.objects.create(jti=jti, resume_id=resume_id, purpose=purpose)
    payload = {
        'user_id': str(resume_id),
        'purpose': purpose,
        'role': 'candidate_action',
        'jti': str(jti),
        'exp': datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _check_action_token_rate_limit(resume_id, purpose, max_per_hour=3):
    cutoff = timezone.now() - timedelta(hours=1)
    count = models.CandidateActionToken.objects.filter(
        resume_id=resume_id, purpose=purpose, created_at__gte=cutoff,
    ).count()
    return count >= max_per_hour


def decode_candidate_action_token(token, expected_purpose):
    if not token:
        return None, Response({'error': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None, Response({'error': 'This link has expired. Request a new one from your application status page.'}, status=status.HTTP_400_BAD_REQUEST)
    except jwt.InvalidTokenError:
        return None, Response({'error': 'Invalid link.'}, status=status.HTTP_400_BAD_REQUEST)

    if payload.get('role') != 'candidate_action' or payload.get('purpose') != expected_purpose:
        return None, Response({'error': 'Invalid link.'}, status=status.HTTP_400_BAD_REQUEST)

    jti = payload.get('jti')
    if not jti:
        return None, Response({'error': 'Invalid link.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        try:
            action_token = models.CandidateActionToken.objects.select_for_update().get(jti=jti)
        except models.CandidateActionToken.DoesNotExist:
            return None, Response(
                {'error': 'This link has already been used or is invalid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if action_token.used_at is not None:
            return None, Response(
                {'error': 'This link has already been used. Request a new one from your application status page.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        action_token.used_at = timezone.now()
        action_token.save(update_fields=['used_at'])

    return payload, None


def _send_candidate_account_link_email(resume, subject, path, action_label):
    full_url = f"{settings.FRONTEND_URL}{path}"
    html_content = f"""
    <html>
        <body>
            <p>Hello {resume.full_name},</p>
            <p>You requested to {action_label} for your EthioGurus application.</p>
            <p>Click the link below to continue. This link expires in 24 hours.</p>
            <p><a href="{full_url}">{action_label}</a></p>
            <p>If you did not request this, you can ignore this email.</p>
        </body>
    </html>
    """
    send_email(resume.email, subject, html_content)


def _auto_verify_email_for_testing(resumes):
    """Mark new applications verified and run screening — mirrors verify_email without token."""
    for resume in resumes:
        resume.is_email_verified = True
        resume.verification_token = ""
        resume.save(update_fields=['is_email_verified', 'verification_token'])
        send_resume_for_screening(resume)


def _mark_testing_skip_stage(resume, stage):
    models.VettingPipelineRecord.objects.update_or_create(
        resume=resume,
        stage=stage,
        defaults={
            'status': 'passed',
            'score': 100,
            'notes': 'Skipped for testing (admin ScreeningConfig).',
        },
    )


def _invite_next_stage_after_screening(resume):
    """After AI screening passes (or is bypassed), invite KYC or theoretical test."""
    if skip_kyc_for_testing():
        _mark_testing_skip_stage(resume, 'kyc')
        if not pipeline_past_stage(resume, 'theoretical_test'):
            trigger_theoretical_test(resume)
    elif not pipeline_past_stage(resume, 'kyc'):
        trigger_kyc_stage(resume)


def send_resume_for_screening(resume):
    applied_position = resume.applied_position

    if skip_ai_screening_for_testing():
        ScreeningResult.objects.create(
            resume=resume,
            score=100,
            passed=True,
            comments='AI screening skipped for testing (admin).',
            position=applied_position,
        )
        models.VettingPipelineRecord.objects.update_or_create(
            resume=resume,
            stage='ai_screening',
            defaults={
                'status': 'passed',
                'score': 100,
                'notes': 'Skipped for testing (admin).',
            },
        )
        _invite_next_stage_after_screening(resume)
        return [100]

    resume_text = extract_text_from_pdf(resume.resume_file.path)
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
            if application_holds_enabled():
                hold_days = 120 if score < 20 else 60 if score < 40 else 30
                hold_until = timezone.now() + timedelta(days=hold_days)
                models.ApplicationOnHold.objects.create(
                    resume=resume,
                    email=resume.email,
                    position=applied_position,
                    hold_until=hold_until,
                    reason=f"AI resume screening failed. Score: {score}. Comments: {comment}",
                )
                _safe_send_application_hold_email(
                    resume,
                    hold_until,
                    context='screening',
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
            _invite_next_stage_after_screening(resume)

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


def trigger_interview_stage(resume):
    if not _invite_pipeline_stage(resume, 'interview', 'invited'):
        return
    html_content = f"""
    <html><body>
    <p>Congratulations! You have passed the theoretical skills assessment for <strong>{resume.applied_position.name}</strong>.</p>
    <p>Our team will reach out to you shortly to schedule your interview.</p>
    <p>Please ensure your contact details are up to date.</p>
    </body></html>
    """
    send_email(resume.email, "Interview Invitation — EthioGig", html_content)


def advance_pipeline(resume, completed_stage):
    try:
        idx = PIPELINE_STAGES.index(completed_stage)
    except ValueError:
        return

    if idx + 1 >= len(PIPELINE_STAGES):
        return

    next_stage = PIPELINE_STAGES[idx + 1]
    if next_stage == 'kyc':
        if skip_kyc_for_testing():
            _mark_testing_skip_stage(resume, 'kyc')
            trigger_theoretical_test(resume)
        else:
            trigger_kyc_stage(resume)
    elif next_stage == 'theoretical_test':
        trigger_theoretical_test(resume)
    elif next_stage == 'interview':
        trigger_interview_stage(resume)


def _hold_days_for_score(score):
    if score is None:
        return 30
    if score < 20:
        return 120
    if score < 40:
        return 60
    return 30


def handle_stage_failure(resume, stage, score):
    if not application_holds_enabled():
        return
    hold_days = _hold_days_for_score(score)
    hold_until = timezone.now() + timedelta(days=hold_days)
    reason = f"Did not meet the threshold for stage '{stage}'. Score: {score}."
    models.ApplicationOnHold.objects.create(
        resume=resume,
        email=resume.email,
        position=resume.applied_position,
        hold_until=hold_until,
        reason=reason,
    )
    _safe_send_application_hold_email(resume, hold_until, context='assessment', reason=reason)


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
def candidate_login_by_email(request):
    """
    Applicant login using the email and password from the freelancer application form.
    Not the same as /api/user/login/ (Django User accounts).
    """
    email = (request.data.get('email') or '').strip()
    password = request.data.get('password')

    if not email or not password:
        return Response(
            {'error': 'Email and password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resumes = models.Resume.objects.filter(email__iexact=email, is_email_verified=True).select_related(
        'applied_position'
    )
    matching = [r for r in resumes if r.check_password(password)]

    if not matching:
        return Response(
            {
                'error': (
                    'No verified application found for this email and password. '
                    'Use the password you set when you applied, and verify your email first.'
                )
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if len(matching) > 1:
        return Response(
            {
                'requires_selection': True,
                'applications': [
                    {
                        'candidate_id': str(r.id),
                        'full_name': r.full_name,
                        'position': r.applied_position.name if r.applied_position else None,
                    }
                    for r in matching
                ],
            },
            status=status.HTTP_200_OK,
        )

    resume = matching[0]
    token = generate_candidate_token(resume)
    return Response(
        {
            'token': token,
            'candidate_id': str(resume.id),
            'full_name': resume.full_name,
            'position': resume.applied_position.name if resume.applied_position else None,
            'expires_in': 7 * 24 * 3600,
        },
        status=status.HTTP_200_OK,
    )


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
def change_candidate_password(request, resume_id):
    """
    Change the application password for a candidate (Resume record).
    Requires candidate Bearer token plus current password.
    """
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not current_password or not new_password:
        return Response(
            {'error': 'current_password and new_password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(new_password) < 5:
        return Response(
            {'error': 'New password must be at least 5 characters.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not resume.check_password(current_password):
        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)

    if current_password == new_password:
        return Response(
            {'error': 'New password must be different from your current password.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resume.password = make_password(new_password)
    resume.save(update_fields=['password'])

    new_token = generate_candidate_token(resume)
    return Response(
        {
            'message': 'Application password updated successfully.',
            'token': new_token,
            'candidate_id': str(resume.id),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def request_password_change_link(request, resume_id):
    """Email a secure link to change the application password."""
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    if _check_action_token_rate_limit(resume.id, 'change_password'):
        return Response(
            {'error': 'Too many requests. Please wait before requesting another password change link.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    token = generate_candidate_action_token(resume.id, 'change_password')
    _send_candidate_account_link_email(
        resume,
        'Change your application password',
        f'application/change-password?token={token}',
        'change your application password',
    )
    return Response(
        {'message': f'A password change link was sent to {resume.email}.'},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def confirm_password_change(request):
    """Complete password change using the token from email."""
    token = request.data.get('token')
    new_password = request.data.get('new_password')

    action_payload, err = decode_candidate_action_token(token, 'change_password')
    if err:
        return err

    if not new_password:
        return Response({'error': 'new_password is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(new_password) < 5:
        return Response(
            {'error': 'New password must be at least 5 characters.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        resume = models.Resume.objects.get(id=action_payload['user_id'])
    except models.Resume.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)

    resume.password = make_password(new_password)
    resume.save(update_fields=['password'])

    return Response(
        {'message': 'Your application password was updated. Sign in again to view your status.'},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def request_email_change_link(request, resume_id):
    """Email a secure link to change the application email address."""
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    if _check_action_token_rate_limit(resume.id, 'change_email'):
        return Response(
            {'error': 'Too many requests. Please wait before requesting another email change link.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    token = generate_candidate_action_token(resume.id, 'change_email')
    _send_candidate_account_link_email(
        resume,
        'Change your application email',
        f'application/change-email?token={token}',
        'change your application email',
    )
    return Response(
        {'message': f'An email change link was sent to {resume.email}.'},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def confirm_email_change(request):
    """Complete email change using the token from email; verifies the new address."""
    token = request.data.get('token')
    new_email = (request.data.get('new_email') or '').strip().lower()

    action_payload, err = decode_candidate_action_token(token, 'change_email')
    if err:
        return err

    if not new_email:
        return Response({'error': 'new_email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resume = models.Resume.objects.get(id=action_payload['user_id'])
    except models.Resume.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)

    if resume.email.lower() == new_email:
        return Response({'error': 'That is already your current email address.'}, status=status.HTTP_400_BAD_REQUEST)

    if models.Resume.objects.filter(email__iexact=new_email, is_email_verified=True).exclude(id=resume.id).exists():
        return Response(
            {'error': 'This email is already used by another verified application.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resume.email = new_email
    resume.is_email_verified = False
    resume.verification_token = get_random_string(32)
    resume.save(update_fields=['email', 'is_email_verified', 'verification_token'])

    send_verification_email(resume)

    return Response(
        {
            'message': (
                f'Your email was updated to {new_email}. '
                'Check your inbox to verify the new address before signing in again.'
            ),
        },
        status=status.HTTP_200_OK,
    )


def _application_hold_message(hold_until):
    return (
        f'Your application is on hold until {hold_until.strftime("%B %d, %Y")}. '
        'You cannot start or continue assessments until the hold period ends. '
        'Check your email for details.'
    )


def _application_hold_email_html(resume, hold_until, *, context='assessment'):
    position_name = resume.applied_position.name if resume.applied_position else 'your application'
    status_url = f"{settings.FRONTEND_URL.rstrip('/')}/application/status?candidate_id={resume.id}"
    context_line = {
        'assessment': 'an assessment stage did not meet the required threshold',
        'proctoring': 'a proctoring policy issue during your assessment',
        'screening': 'your resume did not meet the screening requirements',
        'admin': 'a review decision on your application',
    }.get(context, 'a review decision on your application')
    return f"""
    <html><body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222;">
    <p>Hello {resume.full_name},</p>
    <p>Your application for <strong>{position_name}</strong> is <strong>on hold</strong> because
    {context_line}.</p>
    <p><strong>Hold ends:</strong> {hold_until.strftime('%B %d, %Y')}</p>
    <p>Until then, you cannot start or continue assessments. You may view your status here:</p>
    <p><a href="{status_url}">{status_url}</a></p>
    <p>If you believe this was a mistake, reply to this email or contact support with your
    application email (<strong>{resume.email}</strong>).</p>
    <p>Best regards,<br/>EthioGurus Recruitment</p>
    </body></html>
    """


def _infer_hold_email_context(reason):
    reason_text = (reason or '').lower()
    if 'proctoring' in reason_text or 'camera' in reason_text or 'snapshot' in reason_text:
        return 'proctoring'
    if 'screening' in reason_text:
        return 'screening'
    if 'threshold' in reason_text or 'stage' in reason_text:
        return 'assessment'
    return 'admin'


def _safe_send_application_hold_email(resume, hold_until, *, context='assessment', reason=None):
    if context == 'assessment' and reason:
        context = _infer_hold_email_context(reason)
    try:
        send_email(
            resume.email,
            'Application on hold — EthioGurus',
            _application_hold_email_html(resume, hold_until, context=context),
        )
        return True
    except Exception as exc:
        print(f"Failed to send application hold email to {resume.email}: {exc}")
        return False


def _serialize_application_hold(hold):
    if not hold or not hold.hold_until:
        return {'active': False}
    hold_until = hold.hold_until
    return {
        'active': True,
        'hold_until': hold_until.isoformat(),
        'hold_until_display': hold_until.strftime('%B %d, %Y'),
        'message': _application_hold_message(hold_until),
    }


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def report_proctoring_violation(request, resume_id):
    """
    Records proctoring violations during candidate tests (camera / identity).
    Repeated failures or serious violations place the application on hold.
    """
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    violation_type = (request.data.get('violation_type') or 'pause').strip().lower()
    stage = request.data.get('stage') or 'theoretical_test'
    reason = (request.data.get('reason') or 'Proctoring policy violation').strip()

    if stage not in PIPELINE_STAGES:
        stage = 'theoretical_test'

    if violation_type not in ('pause', 'repeated_pause', 'terminate'):
        return Response(
            {'error': 'Invalid violation_type.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if violation_type == 'pause':
        return Response({'held': False, 'message': 'Recorded.'}, status=status.HTTP_200_OK)

    if not application_holds_enabled():
        return Response(
            {'held': False, 'message': 'Hold policy disabled for testing.'},
            status=status.HTTP_200_OK,
        )

    existing_hold = models.ApplicationOnHold.objects.filter(
        email=resume.email,
        position=resume.applied_position,
        hold_until__gt=timezone.now(),
    ).order_by('-hold_until').first()
    if existing_hold:
        return Response(
            {
                'held': True,
                'hold_until': existing_hold.hold_until.isoformat(),
                'stage': stage,
                'message': _serialize_application_hold(existing_hold).get('message'),
            },
            status=status.HTTP_200_OK,
        )

    hold_days = 30 if violation_type == 'terminate' else 14
    hold_until = timezone.now() + timedelta(days=hold_days)

    models.ApplicationOnHold.objects.create(
        resume=resume,
        email=resume.email,
        position=resume.applied_position,
        hold_until=hold_until,
        reason=reason[:2000],
    )

    record, _ = models.VettingPipelineRecord.objects.get_or_create(
        resume=resume,
        stage=stage,
    )
    record.status = 'on_hold'
    record.notes = (
        f"Proctoring violation ({violation_type}): {reason[:500]}. "
        f"Hold until {hold_until.strftime('%Y-%m-%d')}."
    )
    record.save()

    _safe_send_application_hold_email(
        resume,
        hold_until,
        context='proctoring',
        reason=reason,
    )

    return Response(
        {
            'held': True,
            'hold_until': hold_until.isoformat(),
            'stage': stage,
            'message': _application_hold_message(hold_until),
        },
        status=status.HTTP_200_OK,
    )


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
    hold = active_application_hold(resume)
    hold_payload = _serialize_application_hold(hold)
    if hold:
        hold_payload['email'] = resume.email
    return Response({
        'stages': serializer.data,
        'application_hold': hold_payload,
        'hold_policy': {
            'enforced': application_holds_enabled(),
        },
        'testing_policy': serialize_testing_policy(),
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def resend_hold_notification(request, resume_id):
    """Resend the on-hold notification email for the candidate's active hold."""
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not application_holds_enabled():
        return Response(
            {'error': 'Application holds are disabled for testing.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    hold = models.ApplicationOnHold.objects.filter(
        email=resume.email,
        position=resume.applied_position,
        hold_until__gt=timezone.now(),
    ).order_by('-hold_until').first()
    if not hold:
        return Response(
            {'error': 'There is no active hold on this application.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sent = _safe_send_application_hold_email(
        resume,
        hold.hold_until,
        reason=hold.reason,
    )
    if not sent:
        return Response(
            {
                'error': (
                    'We could not send the email right now. '
                    'Please try again in a few minutes or contact support.'
                ),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response({
        'message': f'Hold notification sent to {resume.email}.',
        'email': resume.email,
        'hold_until': hold.hold_until.isoformat(),
        'hold_until_display': hold.hold_until.strftime('%B %d, %Y'),
    })


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


def _get_or_create_vetting_progress(resume):
    position_name = resume.applied_position.name if resume.applied_position else ''
    progress, _ = models.CandidateVettingProgress.objects.get_or_create(
        resume=resume,
        defaults={'position_name': position_name, 'technology_results': {}},
    )
    if position_name and progress.position_name != position_name:
        progress.position_name = position_name
        progress.save(update_fields=['position_name', 'updated_at'])
    return progress


def _maybe_advance_vetting_stages(resume, progress):
    stack = taxonomy.resolve_stack(progress, resume)
    skills = taxonomy.get_stack_skills(stack, progress, resume)
    if not skills:
        return None

    results = progress.technology_results or {}
    theory_met = taxonomy.required_skills_met(skills, results, 'theoretical')
    theory_count = taxonomy.count_passes_by_kind(skills, results, 'theoretical', required_only=True)
    advanced = []

    if theory_met:
        record, _ = models.VettingPipelineRecord.objects.get_or_create(
            resume=resume, stage='theoretical_test',
        )
        if record.status != 'passed':
            record.status = 'passed'
            record.notes = (
                f'Passed all required theoretical skills ({theory_count}). '
                f'Stack: {progress.selected_stack_name}.'
            )
            record.save()
            advance_pipeline(resume, 'theoretical_test')
            advanced.append('theoretical_test')

    taxonomy.sync_verified_from_results(progress, stack, resume)
    return advanced


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_vetting_stacks(request, resume_id):
    """Returns available stacks for the candidate's applied position."""
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    progress = _get_or_create_vetting_progress(resume)
    stacks, service_taxonomy, uses_db = taxonomy.get_stacks_for_resume(resume)
    service = resume.applied_position

    return Response({
        'position': service.name if service else '',
        'service': service_taxonomy,
        'stacks': stacks,
        'uses_db_taxonomy': uses_db,
        'min_technologies_to_pass': MIN_TECHNOLOGIES_TO_PASS,
        'advancement_rule': 'Pass all required skills in the selected stack.',
        'selected_stack_slug': progress.selected_stack_slug,
        'selected_stack_name': progress.selected_stack_name,
        'selected_stack_id': str(progress.selected_stack_id) if progress.selected_stack_id else None,
    })


@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def vetting_progress(request, resume_id):
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    progress = _get_or_create_vetting_progress(resume)

    if request.method == 'POST':
        stack_slug = (request.data.get('stack_slug') or '').strip()
        stack_id = (request.data.get('stack_id') or '').strip()
        if not stack_slug and not stack_id:
            return Response({'error': 'stack_slug or stack_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        stack_obj = None
        if stack_id:
            stack_obj = models.VettingStack.objects.filter(id=stack_id).first()
        if not stack_obj and stack_slug:
            stack_obj = models.VettingStack.objects.filter(slug=stack_slug).first()
        if not stack_obj:
            stacks, _, _ = taxonomy.get_stacks_for_resume(resume)
            legacy = next((s for s in stacks if s['slug'] == stack_slug), None)
            if not legacy:
                return Response({'error': 'Unknown stack for this position.'}, status=status.HTTP_400_BAD_REQUEST)
            progress.selected_stack_slug = legacy['slug']
            progress.selected_stack_name = legacy['name']
            progress.selected_stack = None
            progress.save(update_fields=['selected_stack_slug', 'selected_stack_name', 'selected_stack', 'updated_at'])
        else:
            progress.selected_stack = stack_obj
            progress.selected_stack_slug = stack_obj.slug
            progress.selected_stack_name = stack_obj.name
            progress.save(update_fields=['selected_stack', 'selected_stack_slug', 'selected_stack_name', 'updated_at'])

        for stage in ('theoretical_test',):
            record, _ = models.VettingPipelineRecord.objects.get_or_create(resume=resume, stage=stage)
            if record.status in ('pending', 'invited'):
                record.status = 'in_progress'
                record.save(update_fields=['status', 'updated_at'])

    stack = taxonomy.resolve_stack(progress, resume)
    skills = taxonomy.get_stack_skills(stack, progress, resume)
    results = progress.technology_results or {}
    theory_passed = taxonomy.count_passes_by_kind(skills, results, 'theoretical', required_only=True)
    practical_passed = taxonomy.count_passes_by_kind(skills, results, 'practical', required_only=True)
    required_count = sum(1 for s in skills if s.get('is_required', True))

    return Response({
        'position': progress.position_name,
        'selected_stack_slug': progress.selected_stack_slug,
        'selected_stack_name': progress.selected_stack_name,
        'selected_stack_id': str(progress.selected_stack_id) if progress.selected_stack_id else None,
        'skills': skills,
        'required_technologies': [s['name'] for s in skills if s.get('is_required', True)],
        'optional_technologies': [s['name'] for s in skills if not s.get('is_required', True)],
        'min_technologies_to_pass': required_count or MIN_TECHNOLOGIES_TO_PASS,
        'advancement_rule': 'Pass all required skills in the selected stack.',
        'technology_results': progress.technology_results,
        'verified_technologies': progress.verified_technologies,
        'certificates': taxonomy.serialize_certificates(resume),
        'counts': {
            'theoretical_passed': theory_passed,
            'practical_passed': practical_passed,
            'required_skill_count': required_count,
            'theoretical_remaining': max(0, required_count - theory_passed),
            'practical_remaining': max(0, required_count - practical_passed),
        },
        'requirements_met': {
            'theoretical': taxonomy.required_skills_met(skills, results, 'theoretical'),
            'practical': taxonomy.required_skills_met(skills, results, 'practical'),
        },
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def report_vetting_tech_result(request, resume_id):
    """
    Records a single technology assessment result (theoretical or practical).
    Advances pipeline stages when minimum passes are met.
    """
    payload, err = _authenticate_candidate(request, resume_id)
    if err:
        return err

    try:
        resume = models.Resume.objects.get(id=resume_id)
    except models.Resume.DoesNotExist:
        return Response({'error': 'Resume not found.'}, status=status.HTTP_404_NOT_FOUND)

    technology = (request.data.get('technology') or '').strip()
    skill_id = (request.data.get('skill_id') or '').strip()
    test_kind = (request.data.get('test_kind') or '').strip().lower()
    passed = request.data.get('passed')
    score = request.data.get('score')
    submission_id = request.data.get('submission_id')
    test_id = request.data.get('test_id')

    if not technology and not skill_id:
        return Response({'error': 'technology or skill_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if test_kind not in ('theoretical', 'practical'):
        return Response({'error': "test_kind must be 'theoretical' or 'practical'."}, status=status.HTTP_400_BAD_REQUEST)
    if passed is None:
        return Response({'error': 'passed is required.'}, status=status.HTTP_400_BAD_REQUEST)

    progress = _get_or_create_vetting_progress(resume)
    if not progress.selected_stack_slug:
        return Response({'error': 'Select an assessment stack before submitting results.'}, status=status.HTTP_400_BAD_REQUEST)

    stack = taxonomy.resolve_stack(progress, resume)
    skill = taxonomy.find_skill_in_stack(stack, progress, resume, technology=technology, skill_id=skill_id)
    if not skill:
        return Response(
            {'error': 'Skill is not part of your selected stack.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    technology = skill['name']

    if test_kind == 'theoretical' and score is not None:
        try:
            config = ScreeningConfig.objects.first()
            threshold = float(config.passing_score_threshold) if config else 70.0
        except Exception:
            threshold = 70.0
        passed = float(score) >= threshold

    if test_kind == 'practical':
        theory_entry = taxonomy._get_skill_result(progress.technology_results or {}, skill).get('theoretical') or {}
        if not theory_entry.get('passed'):
            return Response(
                {'error': f'Pass the theoretical {technology} test before the practical challenge.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    results = dict(progress.technology_results or {})
    results = taxonomy._set_skill_result(results, skill, test_kind, {
        'passed': bool(passed),
        'score': score,
        'submission_id': str(submission_id) if submission_id else None,
        'test_id': str(test_id) if test_id else None,
        'recorded_at': timezone.now().isoformat(),
    })
    progress.technology_results = results
    progress.save(update_fields=['technology_results', 'updated_at'])

    stage_key = 'theoretical_test' if test_kind == 'theoretical' else 'practical_test'
    record, _ = models.VettingPipelineRecord.objects.get_or_create(resume=resume, stage=stage_key)
    if record.status in ('pending', 'invited'):
        record.status = 'in_progress'
        record.save(update_fields=['status', 'updated_at'])

    if not passed:
        record.notes = f'Failed {test_kind} for {technology} (score: {score}). You may retry this test from the hub.'
        record.save(update_fields=['notes', 'updated_at'])
        return Response({
            'recorded': technology,
            'test_kind': test_kind,
            'passed': False,
            'requirements_met': {
                'theoretical': taxonomy.required_skills_met(
                    taxonomy.get_stack_skills(stack, progress, resume),
                    progress.technology_results or {},
                    'theoretical',
                ),
                'practical': taxonomy.required_skills_met(
                    taxonomy.get_stack_skills(stack, progress, resume),
                    progress.technology_results or {},
                    'practical',
                ),
            },
        })

    advanced_stages = _maybe_advance_vetting_stages(resume, progress)
    skills = taxonomy.get_stack_skills(stack, progress, resume)
    results = progress.technology_results or {}
    theory_count = taxonomy.count_passes_by_kind(skills, results, 'theoretical', required_only=True)
    practical_count = taxonomy.count_passes_by_kind(skills, results, 'practical', required_only=True)

    return Response({
        'recorded': technology,
        'skill_id': skill.get('id'),
        'test_kind': test_kind,
        'passed': True,
        'advanced_stages': advanced_stages or [],
        'counts': {
            'theoretical_passed': theory_count,
            'practical_passed': practical_count,
        },
        'requirements_met': {
            'theoretical': taxonomy.required_skills_met(skills, results, 'theoretical'),
            'practical': taxonomy.required_skills_met(skills, results, 'practical'),
        },
        'verified_technologies': progress.verified_technologies,
        'certificates': taxonomy.serialize_certificates(resume),
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

        if application_on_hold.resume and hold_until:
            _safe_send_application_hold_email(
                application_on_hold.resume,
                hold_until,
                context='admin',
                reason=rejection_reason,
            )

        
