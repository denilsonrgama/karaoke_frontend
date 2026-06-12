from django.contrib import admin
from django.utils import timezone

from .models import ContributionPayment


@admin.register(ContributionPayment)
class ContributionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount",
        "access_hours",
        "status",
        "mercado_pago_payment_id",
        "created_at",
        "approved_at",
        "access_until",
        "access_active",
    )
    search_fields = ("user__email", "user__full_name", "mercado_pago_payment_id", "external_reference")
    list_filter = ("status", "created_at", "approved_at")
    readonly_fields = (
        "user",
        "amount",
        "access_hours",
        "status",
        "mercado_pago_payment_id",
        "external_reference",
        "qr_code",
        "qr_code_base64",
        "ticket_url",
        "raw_response",
        "created_at",
        "updated_at",
        "approved_at",
        "access_until",
    )

    def access_active(self, obj):
        return bool(obj.access_until and obj.access_until > timezone.now())

    access_active.boolean = True
    access_active.short_description = "Acesso ativo"
