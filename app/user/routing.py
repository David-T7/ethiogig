from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_id>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/inbox/$', consumers.InboxConsumer.as_asgi()),
    re_path(r'ws/proctor/(?P<session_id>[^/]+)/$', consumers.ProctorSessionConsumer.as_asgi()),
]
