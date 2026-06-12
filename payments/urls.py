from django.urls import path

from . import views


app_name = "payments"

urlpatterns = [
    path("", views.payment_page, name="payment_page"),
    path("criar-pix/", views.create_payment, name="create_payment"),
    path("<int:payment_id>/status/", views.payment_status, name="payment_status"),
    path("mercadopago/webhook/", views.webhook, name="webhook"),
]
