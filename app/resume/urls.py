from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResumeViewSet, ScreeningResultViewSet, ScreeningConfigViewSet   

router = DefaultRouter()
router.register(r'resumes', ResumeViewSet)
router.register(r'screening-results', ScreeningResultViewSet)
router.register(r'screening-config', ScreeningConfigViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
