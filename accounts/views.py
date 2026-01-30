#accounts/views.py
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import render, redirect


from .forms import UserRegisterForm


def register_view(request):
    """
    Cadastro de usuário usando seu UserRegisterForm.
    Renderiza em templates/registration/register.html
    """
    if request.user.is_authenticated:
        return redirect("lista_musicas")  # ✅ já logado, vai pra MUSICAS

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta criada com sucesso! Agora faça login.")
            return redirect("login")  # auth_views.LoginView (name="login")
        else:
            messages.error(request, "Corrija os erros abaixo e tente novamente.")
    else:
        form = UserRegisterForm()

    return render(request, "registration/register.html", {"form": form})



def logout_view(request):
    logout(request)
    return redirect("home")  # ✅ volta pra HOME
