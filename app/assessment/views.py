from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, BasePermission, SAFE_METHODS
from core.models import FullAssessment, Interviewer, FreelancerInterview
from .serializers import FullAssessmentSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication


class IsInterviewer(BasePermission):
    """Allow write access only to users who are Interviewers."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user
            and request.user.is_authenticated
            and Interviewer.objects.filter(id=request.user.id).exists()
        )


class FullAssessmentViewSet(viewsets.ModelViewSet):
    """
    Assessments scoped to the authenticated interviewer's assigned freelancers.
    Only interviewers can write; read is restricted to the same scope.
    """
    serializer_class = FullAssessmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsInterviewer]

    def get_queryset(self):
        user = self.request.user
        if Interviewer.objects.filter(id=user.id).exists():
            freelancer_ids = FreelancerInterview.objects.filter(
                interviewer=user
            ).values_list('freelancer_id', flat=True)
            return FullAssessment.objects.filter(freelancer_id__in=freelancer_ids)
        return FullAssessment.objects.none()
