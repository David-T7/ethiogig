from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FullAssessmentViewSet

router = DefaultRouter()
router.register(r'assessments', FullAssessmentViewSet, basename='fullassessment')

urlpatterns = [
    path('', include(router.urls)),
]
