# app/urls.py
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from musicas import views
from accounts.views import CustomLoginView, admin_dashboard


urlpatterns = [
    path("admin/", admin.site.urls),
    path("site-admin/", admin_dashboard, name="site_admin"),

    # HOME
    path("", views.home, name="home"),

    # APPS
    path("musicas/", include("musicas.urls")),
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),

    # AUTH
    path("accounts/login/", CustomLoginView.as_view(), name="login"),

    # CHANGE PASSWORD
    path("accounts/password_change/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("accounts/password_change/done/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),

    # RESET DE SENHA
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
