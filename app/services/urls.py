# urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServiceViewSet, TechnologyViewSet

router = DefaultRouter()
router.register(r'services', ServiceViewSet)
router.register(r'technologies', TechnologyViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
