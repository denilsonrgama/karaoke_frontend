# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from musicas.models import Musica
from .models import MusicalGenre, SiteConfiguration, User, UserPlay


@admin.register(MusicalGenre)
class MusicalGenreAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = (
        "username",
        "email",
        "full_name",
        "phone",
        "sex",
        "access_status",
        "access_expires_at",
        "song_limit",
        "songs_used",
        "is_staff",
    )
    ordering = ("email",)
    search_fields = ("email", "username", "full_name")
    actions = ["liberar_acesso", "bloquear_acesso"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informacoes pessoais", {
            "fields": ("username", "full_name", "phone", "sex", "musical_genre")
        }),
        ("Acesso ao karaoke", {
            "fields": ("song_limit", "access_expires_at", "access_released")
        }),
        ("Permissoes", {
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

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "full_name", "phone", "sex", "password1", "password2"),
        }),
    )

    filter_horizontal = ("musical_genre",)

    def songs_used(self, obj):
        return obj.song_plays.count()

    songs_used.short_description = "Musicas usadas"

    def access_status(self, obj):
        if obj.is_staff or obj.is_superuser:
            return "Admin"
        if obj.access_released:
            return "Manual"
        if obj.access_expires_at and obj.access_expires_at > timezone.now():
            return "Pago ativo"
        if obj.access_expires_at:
            return "Pago expirado"
        return "Inicial"

    access_status.short_description = "Status do acesso"

    def liberar_acesso(self, request, queryset):
        updated = queryset.update(access_released=True)
        self.message_user(request, f"Acesso liberado para {updated} usuario(s).")

    liberar_acesso.short_description = "Liberar acesso apos contribuicao"

    def bloquear_acesso(self, request, queryset):
        updated = queryset.update(access_released=False)
        self.message_user(request, f"Acesso bloqueado para {updated} usuario(s).")

    bloquear_acesso.short_description = "Bloquear acesso apos limite"


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ("site_name", "allow_registration", "updated_at")


@admin.register(UserPlay)
class UserPlayAdmin(admin.ModelAdmin):
    list_display = ("user", "codigo", "nome", "artista", "played_at")
    search_fields = ("user__email", "user__full_name", "codigo", "nome", "artista")
    readonly_fields = ("user", "codigo", "nome", "artista", "played_at")


@admin.register(Musica)
class MusicaAdmin(admin.ModelAdmin):
    actions = ["zerar_acessos"]

    def zerar_acessos(self, request, queryset):
        queryset.update(acessos=0)
        self.message_user(request, "Acessos zerados com sucesso.")

    zerar_acessos.short_description = "Zerar acessos das musicas selecionadas"
