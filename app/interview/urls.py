from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ( 
    AppointmentViewSet, FreelancerInterviewViewSet, InterviewerViewSet, SelectAppointmentDateView ,
    InterviewerDashboardViewSet , UpdateAppointmentStatusView , InterviewerAppointments , Interivews
)

router = DefaultRouter()
router.register('appointments', AppointmentViewSet, basename='appointment')
router.register('interviews', FreelancerInterviewViewSet, basename='freelancerinterview')
router.register('interviewers', InterviewerViewSet, basename='interviewer')
router.register('interviewer/dashboard', InterviewerDashboardViewSet, basename='interviewer-dashboard')
router.register('interviewer/appointments', InterviewerAppointments, basename='interviewer-appointments')
router.register('interviewer/interviews', Interivews, basename='interviewer-interviews')

urlpatterns = [
    path('', include(router.urls)),
    path('appointments/<uuid:pk>/select-date/', SelectAppointmentDateView.as_view(), name='select-appointment-date'),    
    path('appointments/<uuid:pk>/done/', UpdateAppointmentStatusView.as_view(), name='set-appointment-done'),    

]
