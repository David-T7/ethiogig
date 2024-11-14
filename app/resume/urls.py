from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ResumeViewSet, ScreeningResultViewSet, ScreeningConfigViewSet , FieldViewSet ,
FullAssessmentViewSet , FreelancerFullAssessmentView , FullAssessmentUpdateView)

router = DefaultRouter()
router.register(r'resumes', ResumeViewSet)
router.register(r'screening-results', ScreeningResultViewSet)
router.register(r'screening-config', ScreeningConfigViewSet)
router.register(r'fields', FieldViewSet)
router.register('assessments', FullAssessmentViewSet, basename='fullassessment')

urlpatterns = [
    path('', include(router.urls)),
    path('full-assessment/<uuid:freelancer_id>/', FreelancerFullAssessmentView.as_view(), name='full-assessment'),
    path('full-assessment/<uuid:freelancer_id>/update/', FullAssessmentUpdateView.as_view(), name='full-assessment-update'),
]
