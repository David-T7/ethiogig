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
router.register('dispute-response', views.DisputeResponseViewSet , basename='dispute-response')
router.register('milestones', views.MileStoneViewSet)
router.register('counter-offer', views.CounterOfferView)
router.register('counter-offer-milestones', views.CounterOfferMileStoneViewSet , basename="counter-offer-milestone")
router.register('escrows', views.EscrowViewSet, basename='escrow')
router.register('freelancer-projects', views.FreelancerProjectViewSet , basename='freelancer-projects')
router.register('freelancer-contracts', views.FreelancerContractListViewSet, basename='freelancer-contract-list-view')
router.register('counter-offers', views.CounterOfferViewSet , basename='counter-offers')
router.register('supporting-document', views.SupportingDocumentView),
router.register('drc-disputes',views.DrcForwardedDisputesViewSet)
router.register('dispute-resolve-drc',views.ResolvedDrcViewSet , basename='dispute-resolve-drc')


urlpatterns = [
    path('', include(router.urls)),
    path('freelancer-milestones/project/<uuid:project_id>/', views.FreelancerMilestoneByProjectView.as_view(), name='freelancer-milestones-by-project'),
    path('freelancer-contract/project/<uuid:project_id>/', views.FreelancerContractByProjectView.as_view(), name='freelancer-contract-by-project'),
    path('milestones/project/<uuid:project_id>/', views.MilestoneByProjectView.as_view(), name='milestones-by-project'),
    path('contracts/<uuid:contract_id>/milestones/', views.MilestoneListViewSet.as_view(), name='contract-milestones'),
    path('counter-offer/<uuid:counter_offer_id>/milestones/', views.CounterOfferMilestoneListViewSet.as_view(), name='counter-offer-milestones'),
    path('contracts/<uuid:contract_id>/disputes/', views.DisputeListView.as_view(), name='contract-disputes'),
    path('contracts/<uuid:contract_id>/dispute-responses/', views.DisputeResponseListView.as_view(), name='contract-dispute-responses'),
    path('milestone/<uuid:milestone_id>/disputes/', views.DisputeListView.as_view(), name='milestone-disputes'),
    path('contracts/<uuid:contract_id>/counter-offers/', views.CounterOfferViewSet.as_view({'get': 'list'})),
    path('disputes/<uuid:dispute_id>/cancel/', views.CancelDisputeView.as_view(), name='cancel_dispute'),
    path('freelancer-contracts-update/<uuid:pk>/', views.FreelancerContractViewSet.as_view(), name='freelancer-contract-update'),
    path('freelancer-milestones-update/<uuid:pk>/', views.FreelancerMilestoneViewSet.as_view(), name='freelancer-milestone-update'),
    path('escrows/<uuid:pk>/update-deposit-confirmed/', views.DepositConfirmedUpdateView.as_view(), name='update-deposit-confirmed'),
    path('contracts/<uuid:contract_pk>/escrows/', views.EscrowListView.as_view(), name='contract-escrows-list'),
    path('milestones/<uuid:milestone_pk>/escrows/', views.EscrowMilestoneListView.as_view(), name='milestone-escrows-list'),
    path('projects/<uuid:project_id>/freelancers/', views.ProjectFreelancersView.as_view(), name='project-freelancers'),
    path('projects/<uuid:project_id>/milestones/', views.ProjectMilestonesView.as_view(), name='project-milestones'),
    path('dispute-manager-disputes/',views.DisputeManagerDisputesView.as_view() , name="dispute-manager-disputes") ,   
    path('get-contracts/<uuid:pk>/', views.ContractListView.as_view(), name='contract-list'),
    path('check-active-contract/', views.ActiveContractCheckView.as_view(), name='check-active-contract'),
    path('check-dispute-in-drc/', views.DisputeCheckView.as_view(), name='check_dispute_in_drc'),
]





