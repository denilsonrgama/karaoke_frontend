#accounts/views.py
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from .forms import UserRegisterForm
from django.contrib.auth.views import LoginView



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



def logout_view(request):
    logout(request)
    messages.success(request, "Obrigado! Volte sempre 🤠")
    return redirect("home")