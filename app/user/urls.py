from django.urls import path , include
from . import views
from rest_framework.routers import DefaultRouter

app_name = 'user'

router = DefaultRouter()
router.register('chats', views.ChatViewSet)
router.register('chats/(?P<chat_pk>[^/.]+)/messages', views.MessageViewSet, basename='chat-messages')
router.register('freelancer', views.FreelancerViewSet )
router.register('client', views.ClientViewSet)

urlpatterns = [
    path('freelancer/remove/', views.RemoveFreelancerView.as_view(), name='remove-freelancer'),
    path('client/remove/', views.RemoveClientView.as_view(), name='remove-client'),
    path('token/obtain/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('freelancer/manage/', views.ManageFreelancerView.as_view(), name="manage-freelancer"),
    path('client/manage/', views.ManageClientView.as_view(), name="manage-client"),
    path('projects/', views.ManageProjectListView.as_view(), name="get-projects"),
    path('project/<int:pk>/', views.ManageProjectDetailView.as_view(), name='project-detail'),
    path('clients/', views.ManageClientListView.as_view(), name="get-clients"),
    path('freelancers/', views.ManageFreelnacerListView.as_view(), name="get-freelancers"),
    # path('client/<int:pk>/', views.ManageClientDetailView.as_view(), name='client-detail'),
    # path('freelancer/<int:pk>/', views.ManageFreelancerDetailView.as_view(), name='freelancer-detail'),
    path('', include(router.urls)),
]
