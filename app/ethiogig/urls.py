from drf_spectacular.views import(
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.urls import path

from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/' , SpectacularAPIView.as_view() , name='api-schema'),
    path('api/docs/' ,SpectacularSwaggerView.as_view( url_name = 'api-schema') , name='api-docs'),
    path('api/user/' , include('user.urls')),
    path('api/user/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]