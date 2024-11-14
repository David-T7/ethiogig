# urls.py
from django.urls import path , include
from .views import FreelancerSearchView , ServiceViewSet , TechnologyViewSet , SkillSearchViewSet ,ServicesByFieldView
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'services', ServiceViewSet)
router.register(r'technologies', TechnologyViewSet , basename='technology')
router.register(r'skill-search', SkillSearchViewSet, basename='skill-search')

urlpatterns = [
    path('', include(router.urls)),
    path('freelancers/search/', FreelancerSearchView.as_view(), name='freelancer_search'),
    path('field-services/', ServicesByFieldView.as_view(), name='services-by-field'),
]
