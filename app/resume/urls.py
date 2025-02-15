from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views  # Import views from the current app

router = DefaultRouter()
router.register(r'resumes', views.ResumeViewSet)
router.register(r'screening-results', views.ScreeningResultViewSet)
router.register(r'screening-config', views.ScreeningConfigViewSet)
router.register(r'fields', views.FieldViewSet)
router.register(r'assessments', views.FullAssessmentViewSet, basename='fullassessment')
router.register(r'application-on-hold', views.ApplicationOnHoldViewSet, basename='application-on-hold')  # Ensure this is using views

urlpatterns = [
    path('', include(router.urls)),
    path('full-assessment/<uuid:freelancer_id>/', views.FreelancerFullAssessmentView.as_view(), name='full-assessment'),
    path('full-assessment/<uuid:freelancer_id>/update/', views.FullAssessmentUpdateView.as_view(), name='full-assessment-update'),
    path('not-started-assessments/', views.NotStartedAssessmentsView.as_view(), name='not-started-assessments'),
    path('assign-soft-skills-assessment-appointment/<uuid:freelancer_id>/', views.assign_soft_skills_assessment_appointment, name='assign_soft_skills_assessment_appointment'),
    path('assign-live-assessment-appointment/<uuid:freelancer_id>/', views.assign_live_assessment_appointment, name='assign_live_assessment_appointment'),
    path('activate-full-assessment/<uuid:resume_id>/', views.activate_full_assessment, name='activate_assessment'),
    path('approve_freelancer/<uuid:resume_id>/', views.approve_freelancer, name='approve_freelancer'),
    path('verify-email/', views.verify_email, name='verify-email'),
    path("assessment-termination/", views.AssessmentTerminationView.as_view(), name="assessment-termination"),
]
