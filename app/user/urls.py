from user import views

from django.urls import path

app_name = 'user'
urlpatterns =[
path('createFreelancer/' , view=views.CreateFreelancerView.as_view() , name='createFreelancer') ,
path('createClient/' , view=views.CreateClientView.as_view() , name='createClient') ,
]