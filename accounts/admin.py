# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from musicas.models import Musica
from .models import User, MusicalGenre


@admin.register(MusicalGenre)
class MusicalGenreAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = ("username", "email", "full_name", "phone", "sex", "is_staff")
    ordering = ("email",)
    search_fields = ("email", "username", "full_name")

    # IMPORTANTE: como o login é por email, o campo principal no admin deve ser email
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informações pessoais", {
            "fields": ("username", "full_name", "phone", "sex", "musical_genre")
        }),
        ("Permissões", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )

    # Form de criação no admin
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "full_name", "phone", "sex", "password1", "password2"),
        }),
    )

    filter_horizontal = ("musical_genre",)


@admin.register(Musica)
class MusicaAdmin(admin.ModelAdmin):
    actions = ["zerar_acessos"]

    def zerar_acessos(self, request, queryset):
        queryset.update(acessos=0)
        self.message_user(request, "Acessos zerados com sucesso.")

    zerar_acessos.short_description = "Zerar acessos das músicas selecionadas"
