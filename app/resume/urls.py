from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ResumeViewSet, ScreeningResultViewSet, ScreeningConfigViewSet , FieldViewSet ,
FullAssessmentViewSet , FreelancerFullAssessmentView , FullAssessmentUpdateView , NotStartedAssessmentsView , 
assign_soft_skills_assessment_appointment , activate_full_assessment , approve_freelancer , assign_live_assessment_appointment)

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
    path('not-started-assessments/', NotStartedAssessmentsView.as_view(), name='not-started-assessments'),
    path('assign-soft-skills-assessment-appointment/<uuid:freelancer_id>/',assign_soft_skills_assessment_appointment, name='assign_soft_skills_assessment_appointment'),
    path('assign-live-assessment-appointment/<uuid:freelancer_id>/',assign_live_assessment_appointment, name='assign_live_assessment_appointment'),
    path('activate-full-assessment/<uuid:freelancer_id>/', activate_full_assessment, name='activate_assessment'),
    path('approve_freelancer/<uuid:freelancer_id>/', approve_freelancer, name='approve_freelancer'),
]
