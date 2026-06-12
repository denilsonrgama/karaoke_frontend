import hashlib
import hmac
import uuid
from decimal import Decimal

import requests
from django.conf import settings


MERCADO_PAGO_API_BASE = "https://api.mercadopago.com"


class MercadoPagoError(RuntimeError):
    pass


def get_access_token():
    token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        raise MercadoPagoError("MERCADOPAGO_ACCESS_TOKEN nao configurado")
    return token


def money_to_float(value):
    return float(Decimal(value).quantize(Decimal("0.01")))


def create_pix_payment(payment, notification_url):
    payload = {
        "transaction_amount": money_to_float(payment.amount),
        "description": "Liberacao Karaoke do Cowboy",
        "payment_method_id": "pix",
        "external_reference": payment.external_reference,
        "notification_url": notification_url,
        "payer": {
            "email": payment.user.email,
            "first_name": (payment.user.full_name or payment.user.email).split(" ")[0],
        },
    }
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": payment.external_reference,
    }
    response = requests.post(
        f"{MERCADO_PAGO_API_BASE}/v1/payments",
        json=payload,
        headers=headers,
        timeout=20,
    )
    data = response.json()
    if response.status_code not in (200, 201):
        raise MercadoPagoError(data.get("message") or "Falha ao criar pagamento Pix")

    transaction_data = data.get("point_of_interaction", {}).get("transaction_data", {})
    payment.mercado_pago_payment_id = str(data.get("id") or "")
    payment.status = data.get("status") or payment.status
    payment.qr_code = transaction_data.get("qr_code") or ""
    payment.qr_code_base64 = transaction_data.get("qr_code_base64") or ""
    payment.ticket_url = transaction_data.get("ticket_url") or ""
    payment.raw_response = data
    payment.save()
    return payment


def fetch_payment(payment_id):
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }
    response = requests.get(
        f"{MERCADO_PAGO_API_BASE}/v1/payments/{payment_id}",
        headers=headers,
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        raise MercadoPagoError(data.get("message") or "Falha ao consultar pagamento")
    return data


def make_external_reference(user_id):
    return f"karaoke-{user_id}-{uuid.uuid4()}"


def validate_webhook_signature(request):
    secret = getattr(settings, "MERCADOPAGO_WEBHOOK_SECRET", "")
    if not secret:
        return True

    signature = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    data_id = request.GET.get("data.id") or request.GET.get("id") or ""
    if data_id and not data_id.isdigit():
        data_id = data_id.lower()

    parts = {}
    for part in signature.split(","):
        key, _, value = part.partition("=")
        if key and value:
            parts[key.strip()] = value.strip()

    ts = parts.get("ts")
    received_hash = parts.get("v1")
    if not ts or not received_hash or not request_id or not data_id:
        return False

    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(secret.encode(), msg=manifest.encode(), digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_hash)
