import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import SiteConfiguration
from .models import ContributionPayment
from .services import (
    MercadoPagoError,
    create_pix_payment,
    fetch_payment,
    make_external_reference,
    validate_webhook_signature,
)


def current_pending_payment(user):
    return (
        ContributionPayment.objects
        .filter(user=user, status=ContributionPayment.STATUS_PENDING)
        .exclude(qr_code="")
        .order_by("-created_at")
        .first()
    )


def sync_payment_from_mercado_pago(payment, data):
    status = data.get("status") or payment.status
    payment.status = status
    payment.raw_response = data
    if data.get("id"):
        payment.mercado_pago_payment_id = str(data["id"])
    payment.save(update_fields=["status", "raw_response", "mercado_pago_payment_id", "updated_at"])

    if status == ContributionPayment.STATUS_APPROVED:
        payment.approve()
    return payment


@login_required
def payment_page(request):
    site_config = SiteConfiguration.get_solo()
    payment = current_pending_payment(request.user)
    return render(
        request,
        "payments/payment_page.html",
        {
            "site_config": site_config,
            "payment": payment,
        },
    )


@require_POST
@login_required
def create_payment(request):
    site_config = SiteConfiguration.get_solo()
    payment = current_pending_payment(request.user)
    if payment is None:
        payment = ContributionPayment.objects.create(
            user=request.user,
            amount=site_config.contribution_amount,
            access_hours=site_config.paid_access_hours,
            external_reference=make_external_reference(request.user.id),
        )

    try:
        notification_url = request.build_absolute_uri(reverse("payments:webhook"))
        create_pix_payment(payment, notification_url)
    except MercadoPagoError as exc:
        messages.error(request, str(exc))
    return redirect("payments:payment_page")


@login_required
def payment_status(request, payment_id):
    payment = get_object_or_404(ContributionPayment, pk=payment_id, user=request.user)
    if payment.mercado_pago_payment_id:
        try:
            data = fetch_payment(payment.mercado_pago_payment_id)
            sync_payment_from_mercado_pago(payment, data)
        except MercadoPagoError:
            pass
    return JsonResponse({
        "status": payment.status,
        "approved": payment.status == ContributionPayment.STATUS_APPROVED,
        "access_until": payment.access_until.isoformat() if payment.access_until else None,
    })


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    if not validate_webhook_signature(request):
        return HttpResponse(status=403)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    payment_id = (
        request.GET.get("data.id")
        or request.GET.get("id")
        or body.get("data", {}).get("id")
        or body.get("id")
    )
    topic = request.GET.get("type") or request.GET.get("topic") or body.get("type")
    if topic and topic != "payment":
        return HttpResponse(status=200)
    if not payment_id:
        return HttpResponse(status=200)

    try:
        data = fetch_payment(payment_id)
    except MercadoPagoError:
        return HttpResponse(status=200)

    payment = (
        ContributionPayment.objects
        .filter(mercado_pago_payment_id=str(payment_id))
        .first()
    )
    if payment is None:
        external_reference = data.get("external_reference")
        payment = ContributionPayment.objects.filter(external_reference=external_reference).first()
    if payment is not None:
        sync_payment_from_mercado_pago(payment, data)

    return HttpResponse(status=200)
