from rest_framework import viewsets, status
from rest_framework.response import Response
from .utils import extract_text_from_pdf, score_resume_with_chatgpt, send_resume_result_email, create_freelancer_from_resume
from core.models import Resume, ScreeningResult, ScreeningConfig
from .serializers import ResumeSerializer, ScreeningResultSerializer, ScreeningConfigSerializer
from rest_framework.permissions import AllowAny

class ResumeViewSet(viewsets.ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer

    def create(self, request, *args, **kwargs):
        # Create the resume instance
        response = super().create(request, *args, **kwargs)
        resume = Resume.objects.get(pk=response.data['id'])  # Retrieve the created Resume object
        # Automatically screen the resume after creation
        resume_text = extract_text_from_pdf(resume.resume_file.path)
        position_applied_for = resume.position_applied_for
        score_result = score_resume_with_chatgpt(resume_text, position_applied_for)
        score = score_result['score']
        comment = score_result['comment']

        # Ensure there is a ScreeningConfig instance
        config, created = ScreeningConfig.objects.get_or_create(
            defaults={'passing_score_threshold': 70.0}
        )
        passing_score_threshold = config.passing_score_threshold
        passed = float(score) >= passing_score_threshold

        screening_result = ScreeningResult.objects.create(
            resume=resume,
            score=score,
            passed=passed,
            comments=comment
        )
        send_resume_result_email(resume.email, score, passed, comment)
        if passed:
            create_freelancer_from_resume(resume)

        # Return the original response along with the screening result
        serializer = ScreeningResultSerializer(screening_result)
        response.data['screening_result'] = serializer.data
        return response

class ScreeningResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScreeningResult.objects.all()
    serializer_class = ScreeningResultSerializer

class ScreeningConfigViewSet(viewsets.ModelViewSet):
    queryset = ScreeningConfig.objects.all()
    serializer_class = ScreeningConfigSerializer
