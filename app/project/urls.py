from django.urls import path, include
from rest_framework.routers import DefaultRouter
from project import views

app_name = 'project'

# Create a DefaultRouter instance
router = DefaultRouter()

# Register viewsets with unique basenames
router.register('projects', views.ProjectViewSet)
router.register('contracts', views.ContractViewSet)
router.register('disputes', views.DisputeViewSet)
router.register('contracts/(?P<contract_pk>[0-9a-fA-F-]+)/milestones', views.MilestoneViewSet, basename='contract-milestones')
router.register('escrows', views.EscrowViewSet, basename='escrow')

urlpatterns = [
    path('', include(router.urls)),
    path('freelancer-contracts/', views.FreelancerContractDetialViewSet.as_view(), name='freelancer-contract-detail-view'),
    path('freelancer-contracts/<uuid:pk>/', views.FreelancerContractViewSet.as_view(), name='freelancer-contract-detail'),
    path('escrows/<uuid:pk>/update-deposit-confirmed/', views.DepositConfirmedUpdateView.as_view(), name='update-deposit-confirmed'),
    path('contracts/<uuid:contract_pk>/escrows/', views.EscrowListView.as_view(), name='contract-escrows-list'),
    path('milestones/<uuid:milestone_pk>/escrows/', views.EscrowMilestoneListView.as_view(), name='milestone-escrows-list'),
]
