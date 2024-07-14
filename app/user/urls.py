from django.urls import path
from user import views

app_name = 'user'
urlpatterns = [
    path('freelancer/create/', views.CreateFreelancerView.as_view(), name='createFreelancer'),
    path('client/create/', views.CreateClientView.as_view(), name='createClient'),
    path('freelancer/remove/', views.RemoveFreelancerView.as_view(), name='removeFreelancer'),
    path('client/remove/', views.RemoveClientView.as_view(), name='removeClient'),
    path('token/obtain/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('freelancer/', views.ManageFreelancerView.as_view(), name="getFreelancer"),
    path('client/', views.ManageClientView.as_view(), name="getClient"),
]
