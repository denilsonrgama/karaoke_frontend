#app/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views

from musicas import views


def root_redirect(request):
    if request.user.is_authenticated:
        return redirect("lista_musicas")

    # Se não estiver logado, cair direto na lista (Home real)
    return redirect("home")


urlpatterns = [
    path("admin/", admin.site.urls),

    # ROOT (Home real)
    path("", views.home, name="home"),


    # APPS
    path("musicas/", include("musicas.urls")),
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),

    # AUTH
    path("accounts/login/",auth_views.LoginView.as_view(template_name="registration/login.html"),name="login",),

    # RESET DE SENHA
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
