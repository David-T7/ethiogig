"""
Chapa payment gateway client (https://chapa.co).
Ethiopian payment processing for escrow funding.
"""
import requests
from django.conf import settings

CHAPA_BASE_URL = getattr(settings, 'CHAPA_BASE_URL', 'https://api.chapa.co/v1')


def _headers():
    return {
        'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def initialize_payment(*, amount, currency='ETB', email, first_name, last_name,
                        tx_ref, callback_url, return_url, description=''):
    """
    Initiate a Chapa payment.
    Returns (checkout_url, raw_response) on success.
    Raises RuntimeError on failure.
    """
    payload = {
        'amount': str(amount),
        'currency': currency,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'tx_ref': tx_ref,
        'callback_url': callback_url,
        'return_url': return_url,
        'customization[title]': 'EthioGig Escrow',
        'customization[description]': description or 'Milestone payment',
    }
    resp = requests.post(f'{CHAPA_BASE_URL}/transaction/initialize', json=payload, headers=_headers(), timeout=15)
    data = resp.json()
    if resp.status_code == 200 and data.get('status') == 'success':
        return data['data']['checkout_url'], data
    raise RuntimeError(f"Chapa init failed: {data.get('message', resp.text)}")


def verify_payment(tx_ref):
    """
    Verify a payment by tx_ref.
    Returns the Chapa response dict.
    Raises RuntimeError if verification fails or payment not successful.
    """
    resp = requests.get(f'{CHAPA_BASE_URL}/transaction/verify/{tx_ref}', headers=_headers(), timeout=15)
    data = resp.json()
    if resp.status_code == 200 and data.get('status') == 'success':
        return data
    raise RuntimeError(f"Chapa verify failed: {data.get('message', resp.text)}")


def refund_payment(tx_ref, amount=None):
    """
    Refund a Chapa payment by tx_ref.
    Pass amount for a partial refund; omit for a full refund.
    Raises RuntimeError on failure.
    """
    payload = {'tx_ref': tx_ref}
    if amount is not None:
        payload['amount'] = str(amount)

    resp = requests.post(
        f'{CHAPA_BASE_URL}/refunds',
        json=payload,
        headers=_headers(),
        timeout=15,
    )
    data = resp.json()
    if resp.status_code == 200 and data.get('status') == 'success':
        return data
    raise RuntimeError(f"Chapa refund failed: {data.get('message', resp.text)}")


def transfer_to_bank(*, amount, currency='ETB', account_number, account_name,
                     bank_code='', reference, beneficiary_name=''):
    """
    Send funds to a freelancer's bank account or mobile wallet via Chapa Transfer API.
    Raises RuntimeError on failure.
    """
    payload = {
        'account_number': account_number,
        'amount': str(amount),
        'currency': currency,
        'beneficiary_name': beneficiary_name or account_name,
        'account_name': account_name,
        'reference': reference,
    }
    if bank_code:
        payload['bank_code'] = bank_code

    resp = requests.post(
        f'{CHAPA_BASE_URL}/transfers',
        json=payload,
        headers=_headers(),
        timeout=15,
    )
    data = resp.json()
    if resp.status_code == 200 and data.get('status') == 'success':
        return data
    raise RuntimeError(f"Chapa transfer failed: {data.get('message', resp.text)}")
