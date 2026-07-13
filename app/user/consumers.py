import json
import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import Chat, Message

User = get_user_model()


def _inbox_group(user_id):
    return f'inbox_{user_id}'


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'

        token = self._extract_token()
        if not token:
            await self.close(code=4001)
            return

        user = await self.authenticate(token)
        if user is None:
            await self.close(code=4001)
            return

        self.user_id = user.pk
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        content = (data.get('content') or '').strip()
        if not content:
            return

        message, recipient_id = await self.save_message(content)
        if message is None:
            return

        payload = {
            'type': 'chat_message',
            'id': str(message.id),
            'content': message.content,
            'sender': message.sender_id,
            'timestamp': message.timestamp.isoformat(),
            'file': None,
            'read': False,
        }

        # Broadcast to both chat participants
        await self.channel_layer.group_send(self.room_group_name, payload)

        # Notify recipient's inbox so their chat list updates instantly
        if recipient_id:
            await self.channel_layer.group_send(
                _inbox_group(recipient_id),
                {
                    'type': 'inbox_update',
                    'chat_id': str(self.chat_id),
                    'sender_id': message.sender_id,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                },
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'id': event['id'],
            'content': event['content'],
            'sender': event['sender'],
            'timestamp': event['timestamp'],
            'file': event.get('file'),
            'read': event.get('read', False),
        }))

    # ------------------------------------------------------------------

    def _extract_token(self):
        qs = self.scope.get('query_string', b'').decode('utf-8', errors='ignore')
        for part in qs.split('&'):
            if part.startswith('token='):
                return part[6:]
        return None

    @database_sync_to_async
    def authenticate(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            return User.objects.filter(pk=user_id).first()
        except Exception:
            return None

    @database_sync_to_async
    def save_message(self, content):
        try:
            chat = Chat.objects.select_related('client', 'freelancer').get(id=self.chat_id)
            user = User.objects.get(pk=self.user_id)
            message = Message.objects.create(chat=chat, sender=user, content=content)

            # Determine the other party's ID for inbox notification
            if chat.client_id and str(chat.client_id) != str(self.user_id):
                recipient_id = chat.client_id
            elif chat.freelancer_id and str(chat.freelancer_id) != str(self.user_id):
                recipient_id = chat.freelancer_id
            else:
                recipient_id = None

            return message, recipient_id
        except Exception:
            return None, None


class InboxConsumer(AsyncWebsocketConsumer):
    """
    User-level WebSocket. Client connects once; receives a push whenever
    any new message arrives in any of their chats.
    Route: ws/inbox/?token=<jwt>
    """

    async def connect(self):
        token = self._extract_token()
        if not token:
            await self.close(code=4001)
            return

        user = await self.authenticate(token)
        if user is None:
            await self.close(code=4001)
            return

        self.group_name = _inbox_group(user.pk)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # inbox is receive-only from the server side

    async def inbox_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'chat_id': event['chat_id'],
            'sender_id': event['sender_id'],
            'content': event['content'],
            'timestamp': event['timestamp'],
        }))

    def _extract_token(self):
        qs = self.scope.get('query_string', b'').decode('utf-8', errors='ignore')
        for part in qs.split('&'):
            if part.startswith('token='):
                return part[6:]
        return None

    @database_sync_to_async
    def authenticate(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            return User.objects.filter(pk=user_id).first()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Manual proctoring — WebRTC signaling
# ---------------------------------------------------------------------------

_SIGNAL_TYPES = {'offer', 'answer', 'ice-candidate'}


class ProctorSessionConsumer(AsyncWebsocketConsumer):
    """
    WebRTC signaling channel for one ProctorSession.
    Route: ws/proctor/<session_id>/?token=<jwt>

    Candidate authenticates with the candidate JWT (role='candidate').
    Proctor authenticates with a SimpleJWT access token.
    Messages with type in ('offer', 'answer', 'ice-candidate') are relayed
    to the other party verbatim.
    """

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group = f'proctor_session_{self.session_id}'

        token = self._extract_token()
        if not token:
            await self.close(code=4001)
            return

        role, identity = await self._authenticate(token)
        if role is None:
            await self.close(code=4001)
            return

        valid = await self._validate_access(role, identity)
        if not valid:
            await self.close(code=4003)
            return

        self.role = role
        self.identity = identity

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        if role == 'proctor':
            await self._set_status('proctor_joined')
            await self.channel_layer.group_send(self.room_group, {
                'type': 'session_event',
                'event': 'proctor-joined',
                'exclude': self.channel_name,
            })
        else:
            already_joined = await self._proctor_connected()
            if already_joined:
                await self.send(text_data=json.dumps({'type': 'proctor-joined'}))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
        if getattr(self, 'role', None) == 'proctor':
            await self.channel_layer.group_send(self.room_group, {
                'type': 'session_event',
                'event': 'proctor-left',
                'exclude': self.channel_name,
            })

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        msg_type = data.get('type')

        if msg_type in _SIGNAL_TYPES:
            await self.channel_layer.group_send(self.room_group, {
                'type': 'relay_signal',
                'signal': data,
                'exclude': self.channel_name,
            })
        elif msg_type == 'session-active':
            await self._set_status('active', set_started=True)

    async def relay_signal(self, event):
        if event.get('exclude') == self.channel_name:
            return
        await self.send(text_data=json.dumps(event['signal']))

    async def session_event(self, event):
        if event.get('exclude') == self.channel_name:
            return
        await self.send(text_data=json.dumps({'type': event['event']}))

    # ------------------------------------------------------------------

    def _extract_token(self):
        qs = self.scope.get('query_string', b'').decode('utf-8', errors='ignore')
        for part in qs.split('&'):
            if part.startswith('token='):
                return part[6:]
        return None

    @database_sync_to_async
    def _authenticate(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('role') == 'candidate':
                return 'candidate', payload['user_id']
        except Exception:
            pass
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from core.models import Proctor
            tok = AccessToken(token)
            user_id = tok['user_id']
            if Proctor.objects.filter(pk=user_id).exists():
                return 'proctor', user_id
        except Exception:
            pass
        return None, None

    @database_sync_to_async
    def _validate_access(self, role, identity):
        from core.models import ProctorSession
        try:
            session = ProctorSession.objects.get(id=self.session_id)
            if role == 'candidate':
                return str(session.resume_id) == str(identity)
            return session.proctor_id is not None and str(session.proctor_id) == str(identity)
        except ProctorSession.DoesNotExist:
            return False

    @database_sync_to_async
    def _proctor_connected(self):
        from core.models import ProctorSession
        try:
            return ProctorSession.objects.filter(
                id=self.session_id, status__in=['proctor_joined', 'active'],
            ).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _set_status(self, new_status, set_started=False):
        from core.models import ProctorSession
        update = {'status': new_status}
        if set_started:
            update['started_at'] = timezone.now()
        ProctorSession.objects.filter(id=self.session_id).update(**update)
