"""
Chapa payment endpoints for escrow funding.

POST /api/payments/escrow/{escrow_id}/initialize/   — client initiates payment
GET  /api/payments/escrow/{escrow_id}/verify/       — verify & confirm escrow deposit
POST /api/payments/webhook/                         — Chapa server-to-server callback
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import Escrow, Client
from . import chapa as chapa_client

logger = logging.getLogger(__name__)

TX_REF_PREFIX = 'ethiogig-escrow-'


def _verify_chapa_signature(request):
    """Return True if the Chapa webhook signature is valid (or no secret is configured)."""
    secret = getattr(settings, 'CHAPA_WEBHOOK_SECRET', '')
    if not secret:
        return True  # skip in dev when secret not configured
    sig = request.META.get('HTTP_X_CHAPA_SIGNATURE', '')
    expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _tx_ref(escrow_id):
    return f'{TX_REF_PREFIX}{escrow_id}'


def _escrow_from_tx_ref(tx_ref):
    if not tx_ref.startswith(TX_REF_PREFIX):
        return None
    escrow_id = tx_ref[len(TX_REF_PREFIX):]
    return Escrow.objects.filter(id=escrow_id).first()


class InitializeEscrowPaymentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, escrow_id):
        escrow = Escrow.objects.filter(id=escrow_id).first()
        if not escrow:
            return Response({'error': 'Escrow not found.'}, status=status.HTTP_404_NOT_FOUND)

        if escrow.deposit_confirmed:
            return Response({'error': 'Escrow already funded.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(pk=request.user.pk)
        except Client.DoesNotExist:
            return Response({'error': 'Only clients can fund escrows.'}, status=status.HTTP_403_FORBIDDEN)

        if escrow.contract.client != client:
            return Response({'error': 'This escrow does not belong to your contract.'}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        first_name = getattr(user, 'first_name', '') or 'Client'
        last_name = getattr(user, 'last_name', '') or ''

        backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000')
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000/')

        try:
            checkout_url, _ = chapa_client.initialize_payment(
                amount=escrow.amount,
                currency='ETB',
                email=user.email,
                first_name=first_name,
                last_name=last_name,
                tx_ref=_tx_ref(escrow.id),
                callback_url=f'{backend_url}/api/payments/webhook/',
                return_url=f'{frontend_url}payment-success?escrow_id={escrow.id}',
                description=f'Milestone escrow #{escrow.id}',
            )
        except RuntimeError as exc:
            logger.error('Chapa init error for escrow %s: %s', escrow.id, exc)
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({'checkout_url': checkout_url, 'tx_ref': _tx_ref(escrow.id)})


class VerifyEscrowPaymentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, escrow_id):
        escrow = Escrow.objects.filter(id=escrow_id).first()
        if not escrow:
            return Response({'error': 'Escrow not found.'}, status=status.HTTP_404_NOT_FOUND)

        tx_ref = _tx_ref(escrow.id)
        try:
            data = chapa_client.verify_payment(tx_ref)
        except RuntimeError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        payment_status = data.get('data', {}).get('status', '')
        if payment_status == 'success' and not escrow.deposit_confirmed:
            escrow.deposit_confirmed = True
            escrow.save(update_fields=['deposit_confirmed'])

        return Response({
            'deposit_confirmed': escrow.deposit_confirmed,
            'chapa_status': payment_status,
        })


@method_decorator(csrf_exempt, name='dispatch')
class ChapaWebhookView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not _verify_chapa_signature(request):
            logger.warning('Chapa webhook received with invalid signature')
            return Response({'error': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return Response({'error': 'Invalid JSON.'}, status=status.HTTP_400_BAD_REQUEST)

        tx_ref = payload.get('tx_ref', '')
        event_status = payload.get('status', '')

        if event_status != 'success' or not tx_ref:
            return Response({'received': True})

        # Verify payment server-side (don't trust the webhook payload alone)
        try:
            data = chapa_client.verify_payment(tx_ref)
            verified_status = data.get('data', {}).get('status', '')
        except RuntimeError as exc:
            logger.warning('Chapa webhook verify failed for tx_ref %s: %s', tx_ref, exc)
            return Response({'received': True})

        if verified_status != 'success':
            return Response({'received': True})

        escrow = _escrow_from_tx_ref(tx_ref)
        if escrow and not escrow.deposit_confirmed:
            escrow.deposit_confirmed = True
            escrow.save(update_fields=['deposit_confirmed'])
            logger.info('Escrow %s deposit confirmed via webhook', escrow.id)

        return Response({'received': True})
