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
    # Candidate pipeline — must be listed before router.urls (resumes/<pk>/ would swallow these)
    path('resumes/candidate-login/', views.candidate_login_by_email, name='candidate-login'),
    path('resumes/confirm-password-change/', views.confirm_password_change, name='confirm-password-change'),
    path('resumes/confirm-email-change/', views.confirm_email_change, name='confirm-email-change'),
    path('resumes/<uuid:resume_id>/candidate-token/', views.get_candidate_token, name='candidate-token'),
    path('resumes/<uuid:resume_id>/change-password/', views.change_candidate_password, name='change-candidate-password'),
    path('resumes/<uuid:resume_id>/request-password-change/', views.request_password_change_link, name='request-password-change'),
    path('resumes/<uuid:resume_id>/request-email-change/', views.request_email_change_link, name='request-email-change'),
    path('resumes/<uuid:resume_id>/proctoring-violation/', views.report_proctoring_violation, name='proctoring-violation'),
    path('resumes/<uuid:resume_id>/pipeline-stage/', views.report_stage_result, name='report-stage-result'),
    path('resumes/<uuid:resume_id>/pipeline-status/', views.get_pipeline_status, name='pipeline-status'),
    path('resumes/<uuid:resume_id>/candidate-info/', views.get_candidate_info, name='candidate-info'),
    path('resumes/<uuid:resume_id>/vetting-stacks/', views.get_vetting_stacks, name='vetting-stacks'),
    path('resumes/<uuid:resume_id>/vetting-progress/', views.vetting_progress, name='vetting-progress'),
    path('resumes/<uuid:resume_id>/vetting-tech-result/', views.report_vetting_tech_result, name='vetting-tech-result'),
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
