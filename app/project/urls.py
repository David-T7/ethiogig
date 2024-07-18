from django.urls import path, include
from rest_framework.routers import DefaultRouter
from project import views

# Create a DefaultRouter instance
router = DefaultRouter()

# Register viewsets with unique basenames
router.register('projects', views.ProjectViewSet, basename='project')
router.register('contracts', views.ContractViewSet, basename='contract')
router.register('disputes', views.DisputeViewSet, basename='dispute')

# Define the app name for namespace
app_name = 'project'

# Define urlpatterns to include router's URLs
urlpatterns = [
    path('', include(router.urls)),
    path('freelancer-contracts/', views.FreelancerContractDetialViewSet.as_view(), name='freelancer-contract-detail-view'),
    path('freelancer-contracts/<int:pk>/', views.FreelancerContractViewSet.as_view(), name='freelancer-contract-detail'),

]
