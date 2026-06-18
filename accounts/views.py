# accounts/views.py
import os
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from musicas.models import Musica
from payments.models import ContributionPayment
from .forms import SiteConfigurationForm, UserRegisterForm
from .models import AuditEvent, SiteConfiguration, User


def duration_label(seconds):
    seconds = int(seconds or 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}min {rest}s" if rest else f"{minutes}min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}min" if minutes else f"{hours}h"


class CustomLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditEvent.log_from_request(
            self.request,
            AuditEvent.LOGIN_SUCCESS,
            user=self.request.user,
        )
        login_message = "Login realizado com sucesso. Seja bem vindo!"
        storage = messages.get_messages(self.request)
        existing_messages = [
            message
            for message in storage
            if str(message) != login_message
        ]
        for message in existing_messages:
            messages.add_message(self.request, message.level, str(message), extra_tags=message.extra_tags)
        messages.success(self.request, login_message)
        return response

    def form_invalid(self, form):
        email = self.request.POST.get("username") or self.request.POST.get("email") or ""
        AuditEvent.log_from_request(
            self.request,
            AuditEvent.LOGIN_FAILURE,
            email=email,
        )
        return super().form_invalid(form)

    def get_success_url(self):
        redirect_to = self.get_redirect_url() or resolve_url(settings.LOGIN_REDIRECT_URL)
        query = urlencode({"next": redirect_to})
        return f"{reverse('accounts:welcome')}?{query}"


def csrf_failure(request, reason=""):
    messages.warning(
        request,
        "Sua sessao expirou. Abra o login novamente e tente entrar mais uma vez.",
    )
    next_url = request.POST.get("next") or request.GET.get("next") or settings.LOGIN_REDIRECT_URL
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = settings.LOGIN_REDIRECT_URL
    return redirect(f"{reverse('login')}?{urlencode({'next': next_url})}")


@login_required
def welcome_view(request):
    next_url = request.GET.get("next") or resolve_url(settings.LOGIN_REDIRECT_URL)
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = resolve_url(settings.LOGIN_REDIRECT_URL)

    name = (
        getattr(request.user, "first_name", "")
        or getattr(request.user, "full_name", "")
        or getattr(request.user, "username", "")
        or "Cowboy"
    )
    display_name = name.strip().split()[0] if name.strip() else "Cowboy"

    return render(
        request,
        "accounts/welcome.html",
        {"next_url": next_url, "display_name": display_name},
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    site_config = SiteConfiguration.get_solo()
    if not site_config.allow_registration:
        messages.warning(request, "Novos cadastros estao temporariamente fechados.")
        return redirect("home")

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.song_limit = int(getattr(settings, "FREE_SONG_LIMIT", 2))
            user.save()
            form.save_m2m()
            messages.success(
                request,
                f"Conta criada com sucesso! Voce tem {user.song_limit} musicas iniciais liberadas.",
            )
            return redirect("home")
        messages.error(request, "Corrija os erros abaixo e tente novamente.")
    else:
        form = UserRegisterForm()

    return render(request, "registration/register.html", {"form": form})


@staff_member_required
def admin_dashboard(request):
    from musicas.views import tone_cache_dir

    site_config = SiteConfiguration.get_solo()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_config":
            form = SiteConfigurationForm(request.POST, instance=site_config)
            if form.is_valid():
                form.save()
                messages.success(request, "Configuracoes salvas com sucesso.")
                return redirect("site_admin")
            messages.error(request, "Corrija os campos destacados.")
        elif action == "clear_tone_cache":
            removed = 0
            cache_dir = tone_cache_dir()
            for name in os.listdir(cache_dir):
                path = os.path.join(cache_dir, name)
                if os.path.isfile(path) and name.endswith((".mp4", ".part")):
                    os.remove(path)
                    removed += 1
            messages.success(request, f"Cache de tons limpo: {removed} arquivo(s) removido(s).")
            return redirect("site_admin")
        else:
            form = SiteConfigurationForm(instance=site_config)
    else:
        form = SiteConfigurationForm(instance=site_config)

    cache_total = 0
    cache_count = 0
    cache_dir = tone_cache_dir()
    for name in os.listdir(cache_dir):
        path = os.path.join(cache_dir, name)
        if os.path.isfile(path) and name.endswith(".mp4"):
            cache_count += 1
            cache_total += os.path.getsize(path)

    context = {
        "form": form,
        "site_config": site_config,
        "total_users": User.objects.count(),
        "staff_users": User.objects.filter(is_staff=True).count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "paid_active_users": User.objects.filter(access_expires_at__gt=timezone.now()).count(),
        "approved_payments": ContributionPayment.objects.filter(
            status=ContributionPayment.STATUS_APPROVED
        ).count(),
        "pending_payments": ContributionPayment.objects.filter(
            status=ContributionPayment.STATUS_PENDING
        ).count(),
        "total_musicas": Musica.objects.count(),
        "top_musicas": Musica.objects.order_by("-acessos", "nome")[:5],
        "tone_cache_count": cache_count,
        "tone_cache_mb": round(cache_total / 1024 / 1024, 1),
    }
    return render(request, "accounts/admin_dashboard.html", context)


@staff_member_required
def audit_dashboard(request):
    now = timezone.now()
    start = now - timedelta(days=30)
    events = AuditEvent.objects.filter(created_at__gte=start)
    watch_events = events.filter(event_type=AuditEvent.VIDEO_WATCH)
    access_events = events.exclude(event_type=AuditEvent.VIDEO_WATCH)

    total_watch_seconds = watch_events.aggregate(total=Sum("duration_seconds"))["total"] or 0
    summary = {
        "login_success": events.filter(event_type=AuditEvent.LOGIN_SUCCESS).count(),
        "login_failure": events.filter(event_type=AuditEvent.LOGIN_FAILURE).count(),
        "song_plays": events.filter(event_type=AuditEvent.MUSIC_PLAY).count(),
        "music_details": events.filter(event_type=AuditEvent.MUSIC_DETAIL).count(),
        "list_views": events.filter(event_type=AuditEvent.LIST_VIEW).count(),
        "watch_label": duration_label(total_watch_seconds),
        "watch_seconds": total_watch_seconds,
    }

    top_songs = (
        events.filter(event_type=AuditEvent.MUSIC_PLAY)
        .values("codigo", "nome", "artista")
        .annotate(total=Count("id"))
        .order_by("-total", "nome")[:10]
    )
    watch_by_song = list(
        watch_events.values("codigo", "nome", "artista")
        .annotate(total_seconds=Sum("duration_seconds"), views=Count("id"))
        .order_by("-total_seconds", "nome")[:10]
    )
    for item in watch_by_song:
        item["watch_label"] = duration_label(item["total_seconds"])
    events_by_day = (
        access_events.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Count("id"),
            logins=Count("id", filter=Q(event_type=AuditEvent.LOGIN_SUCCESS)),
            plays=Count("id", filter=Q(event_type=AuditEvent.MUSIC_PLAY)),
            failures=Count("id", filter=Q(event_type=AuditEvent.LOGIN_FAILURE)),
        )
        .order_by("-day")[:14]
    )
    recent_events = access_events.select_related("user").order_by("-created_at")[:40]
    recent_watch_events = watch_events.select_related("user").order_by("-created_at")[:40]

    context = {
        "summary": summary,
        "top_songs": top_songs,
        "watch_by_song": watch_by_song,
        "events_by_day": events_by_day,
        "recent_events": recent_events,
        "recent_watch_events": recent_watch_events,
        "period_label": "ultimos 30 dias",
    }
    return render(request, "accounts/audit_dashboard.html", context)


def logout_view(request):
    if request.user.is_authenticated:
        AuditEvent.log_from_request(request, AuditEvent.LOGOUT, user=request.user)
    logout(request)
    messages.success(request, "Obrigado! Volte sempre.")
    return redirect("home")
