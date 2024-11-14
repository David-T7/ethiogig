from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from core.models import FullAssessment
from .serializers import FullAssessmentSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsInterviewerOrReadOnly(BasePermission):
    """
    Custom permission to allow only interviewers to modify, while others can view.
    """

    def has_permission(self, request, view):
        # Allow read-only access to all users
        if request.method in SAFE_METHODS:
            return True
        # Allow modifications only if the user is authenticated and has the 'interviewer' role
        return request.user and request.user.is_authenticated and request.user.role == 'interviewer'


class FullAssessmentViewSet(viewsets.ModelViewSet):
    """
    A viewset that provides the standard actions for FullAssessment.
    Only users with the 'interviewer' role can create, update, or delete.
    """
    queryset = FullAssessment.objects.all()
    serializer_class = FullAssessmentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsInterviewerOrReadOnly]
