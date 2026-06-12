from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ContributionPayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_ERROR = "error"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pendente"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_REJECTED, "Rejeitado"),
        (STATUS_CANCELLED, "Cancelado"),
        (STATUS_EXPIRED, "Expirado"),
        (STATUS_ERROR, "Erro"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    access_hours = models.PositiveIntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    mercado_pago_payment_id = models.CharField(max_length=80, blank=True, db_index=True)
    external_reference = models.CharField(max_length=80, unique=True)
    qr_code = models.TextField(blank=True)
    qr_code_base64 = models.TextField(blank=True)
    ticket_url = models.URLField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    access_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pagamento de contribuicao"
        verbose_name_plural = "Pagamentos de contribuicao"

    def __str__(self):
        return f"{self.user} - R$ {self.amount} - {self.status}"

    def approve(self):
        now = timezone.now()
        current_until = self.user.access_expires_at
        base_time = current_until if current_until and current_until > now else now
        self.status = self.STATUS_APPROVED
        self.approved_at = self.approved_at or now
        self.access_until = base_time + timedelta(hours=self.access_hours)
        self.save(update_fields=["status", "approved_at", "access_until", "updated_at"])

        self.user.access_expires_at = self.access_until
        self.user.save(update_fields=["access_expires_at"])
