import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import user.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ethiogig.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': URLRouter(user.routing.websocket_urlpatterns),
})
