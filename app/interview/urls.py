from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AppointmentViewSet, FreelancerInterviewViewSet, InterviewerViewSet, SelectAppointmentDateView

router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'interviews', FreelancerInterviewViewSet, basename='freelancerinterview')
router.register(r'interviewers', InterviewerViewSet, basename='interviewer')

urlpatterns = [
    path('', include(router.urls)),
    path('appointments/<int:pk>/select-date/', SelectAppointmentDateView.as_view(), name='select-appointment-date'),

]
