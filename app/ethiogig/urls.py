from drf_spectacular.views import(
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.urls import path
from user import views
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
# from resume.views import verify_email


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/' , SpectacularAPIView.as_view() , name='api-schema'),
    path('api/docs/' ,SpectacularSwaggerView.as_view( url_name = 'api-schema') , name='api-docs'),
    path('api/user/' , include('user.urls')),
    path('api/' , include('resume.urls')),
    path('api/' , include('interview.urls')),
    path('api/' , include('services.urls')),
    path('api/' , include('project.urls')),
    path('api/' , include('assessment.urls')),
    path('api/user/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('reset-password/<uidb64>/<token>/',views.reset_password, name='reset-password'),
    path('password-reset-request/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),
    # path('verify-email/<uidb64>/<token>/', verify_email, name='verify_email'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
