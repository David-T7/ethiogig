from django.urls import path , include
from . import views
from rest_framework.routers import DefaultRouter

app_name = 'user'

router = DefaultRouter()
router.register('chats', views.ChatViewSet)
router.register('freelancer', views.FreelancerViewSet )
router.register('client', views.ClientViewSet)
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('message', views.MessageViewSet, basename='message')

urlpatterns = [
    path('clientFreelancerChat/', views.ChatBetweenClientFreelancerView.as_view(), name='chat-client-freelancer'),
    path('clientChats/', views.ClientChatListView.as_view(), name='client-chats'),
    path('freelancerChats/', views.FreelancerChatListView.as_view(), name='freelancer-chats'),
    path('clientChats/', views.ClientChatListView.as_view(), name='client-chats'),
    path('chats/<uuid:chat_pk>/messages/', views.MessageViewSet.as_view({'post': 'create'})),
    path('freelancer/remove/', views.RemoveFreelancerView.as_view(), name='remove-freelancer'),
    path('client/remove/', views.RemoveClientView.as_view(), name='remove-client'),
    path('token/obtain/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token_refresh'),
    path('token/authenticate/', views.AuthenticateView.as_view(), name='token_authenticate'),
    path('freelancer/manage/', views.ManageFreelancerView.as_view(), name="manage-freelancer"),
    path('interviewer/manage/', views.ManageInterviewerView.as_view(), name="manage-interviewer"),
    path('dispute-manager/manage/', views.ManageDisputeMangerView.as_view(), name="manage-dispute-manager"),
    path('resume-check/manage/', views.ManageResumeCheckerView.as_view(), name="resume-check-manager"),
    path('client/manage/', views.ManageClientView.as_view(), name="manage-client"),
    path('projects/', views.ManageProjectListView.as_view(), name="get-projects"),
    path('project/<uuid:pk>/', views.ManageProjectDetailView.as_view(), name='project-detail'),
    path('clients/', views.ManageClientListView.as_view(), name="get-clients"),
    path('freelancers/', views.ManageFreelnacerListView.as_view(), name="get-freelancers"),
    path('login/', views.LoginView.as_view(), name='login'),
    path('role/', views.UserRoleView.as_view(), name='user-role'),
    path('messages/unread-count/', views.unread_message_count, name='unread_message_count'),
    path('notifications/unread-count/', views.unread_notification_count, name='unread_notification_count'),
    path('change-password/', views.PasswordChangeView.as_view(), name='change-password'),
    path('select-appointment/', views.SelectAppointmentDateView.as_view(), name='select-appointment'),
    path('messages/read/', views.MarkMessagesAsReadView.as_view(), name='mark-messages-as-read'),
    path('verify-skills/', views.VerifyFreelancerSkillsView.as_view(), name='verify-freelnacer-skills'),
    path('user-type/', views.UserTypeView.as_view(), name='user-type'),
    path('verify-email/', views.verify_email, name='verify-email'),
    # path('client/<int:pk>/', views.ManageClientDetailView.as_view(), name='client-detail'),
    # path('freelancer/<int:pk>/', views.ManageFreelancerDetailView.as_view(), name='freelancer-detail'),
    path('send-verification-link/', views.send_email_verification_link, name='send-verification-link'),
    path('send-email/', views.send_email_, name='send-email'),
    path('sign-up/', views.sign_up, name='sign_up'),
    path("waitlist/", views.WaitlistCreateView.as_view(), name="waitlist"),
    path('', include(router.urls)),
]
