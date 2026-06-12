#accounts/views.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from musicas.models import Musica
from .forms import SiteConfigurationForm, UserRegisterForm
from .models import SiteConfiguration, User
from django.contrib.auth.views import LoginView
import os



class CustomLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Login realizado com sucesso. Seja bem vindo!")
        return response

    def get_success_url(self):
        # sempre volta pra HOME
        return "/"



def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")  # ✅ já logado, fica na HOME


    site_config = SiteConfiguration.get_solo()
    if not site_config.allow_registration:
        messages.warning(request, "Novos cadastros estao temporariamente fechados.")
        return redirect("home")

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta criada com sucesso! Agora faça login.")
            return redirect("home")  # auth_views.LoginView (name="login")
        else:
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
        "total_musicas": Musica.objects.count(),
        "top_musicas": Musica.objects.order_by("-acessos", "nome")[:5],
        "tone_cache_count": cache_count,
        "tone_cache_mb": round(cache_total / 1024 / 1024, 1),
    }
    return render(request, "accounts/admin_dashboard.html", context)


def logout_view(request):
    logout(request)
    messages.success(request, "Obrigado! Volte sempre 🤠")
    return redirect("home")
