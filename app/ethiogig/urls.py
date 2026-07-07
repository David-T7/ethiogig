from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenRefreshView
from django.urls import path, include
from user import views
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from project.payment_views import (
    InitializeEscrowPaymentView,
    VerifyEscrowPaymentView,
    ChapaWebhookView,
)
from project.views import CancelContractView, FreelancerCancelContractView, ApproveMilestoneView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    path('api/user/', include('user.urls')),
    path('api/', include('resume.urls')),
    path('api/', include('interview.urls')),
    path('api/', include('services.urls')),
    path('api/', include('project.urls')),
    path('api/', include('assessment.urls')),
    path('api/user/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('reset-password/<uidb64>/<token>/', views.reset_password, name='reset-password'),
    path('password-reset-request/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),

    # Contract cancellation
    path('api/contracts/<uuid:pk>/cancel/', CancelContractView.as_view(), name='contract-cancel'),
    path('api/contracts/<uuid:pk>/freelancer-cancel/', FreelancerCancelContractView.as_view(), name='contract-freelancer-cancel'),
    path('api/milestones/<uuid:pk>/approve/', ApproveMilestoneView.as_view(), name='milestone-approve'),

    # Chapa payment endpoints
    path('api/payments/escrow/<uuid:escrow_id>/initialize/', InitializeEscrowPaymentView.as_view(), name='chapa-init'),
    path('api/payments/escrow/<uuid:escrow_id>/verify/', VerifyEscrowPaymentView.as_view(), name='chapa-verify'),
    path('api/payments/webhook/', ChapaWebhookView.as_view(), name='chapa-webhook'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
