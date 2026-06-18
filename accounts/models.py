#accounts/models.py
from decimal import Decimal

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class MusicalGenre(models.Model):
    name = models.CharField("Gênero musical", max_length=100)

    class Meta:
        verbose_name = "Gênero musical"
        verbose_name_plural = "Gêneros musicais"

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O email é obrigatório")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa ter is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = models.CharField("username", max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField("Email", unique=True)
    full_name = models.CharField("Nome completo", max_length=150)
    phone = models.CharField("Telefone", max_length=20)

    SEX_CHOICES = (
        ("M", "Masculino"),
        ("F", "Feminino"),
        ("O", "Outro"),
    )
    sex = models.CharField("Sexo", max_length=1, choices=SEX_CHOICES)
    song_limit = models.PositiveIntegerField("Limite inicial de musicas", default=2)
    access_released = models.BooleanField("Acesso liberado pelo admin", default=False)
    access_expires_at = models.DateTimeField("Acesso pago expira em", null=True, blank=True)

    musical_genre = models.ManyToManyField(
    MusicalGenre,
    blank=True,
    verbose_name="Gêneros musicais favoritos",
)


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class MusicaEstatistica(models.Model):
    codigo = models.CharField(max_length=20)
    nome = models.CharField(max_length=200)
    artista = models.CharField(max_length=200)
    acessos = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-acessos"]

    def __str__(self):
        return f"{self.nome} - {self.artista}"


class UserPlay(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="song_plays")
    codigo = models.CharField(max_length=20)
    nome = models.CharField(max_length=200, blank=True)
    artista = models.CharField(max_length=200, blank=True)
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Musica cantada por usuario"
        verbose_name_plural = "Musicas cantadas por usuarios"
        unique_together = ("user", "codigo")
        ordering = ["-played_at"]

    def __str__(self):
        return f"{self.codigo} - {self.user_id}"


class AuditEvent(models.Model):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    LIST_VIEW = "list_view"
    MUSIC_DETAIL = "music_detail"
    MUSIC_PLAY = "music_play"
    VIDEO_WATCH = "video_watch"

    EVENT_CHOICES = (
        (LOGIN_SUCCESS, "Login com sucesso"),
        (LOGIN_FAILURE, "Falha de login"),
        (LOGOUT, "Logout"),
        (LIST_VIEW, "Tela de busca"),
        (MUSIC_DETAIL, "Detalhe da musica"),
        (MUSIC_PLAY, "Musica iniciada"),
        (VIDEO_WATCH, "Tempo de visualizacao"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    email = models.EmailField(blank=True)
    codigo = models.CharField(max_length=20, blank=True)
    nome = models.CharField(max_length=200, blank=True)
    artista = models.CharField(max_length=200, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    path = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Evento de auditoria"
        verbose_name_plural = "Eventos de auditoria"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["codigo", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.created_at:%d/%m/%Y %H:%M}"

    @property
    def duration_label(self):
        seconds = int(self.duration_seconds or 0)
        if seconds < 60:
            return f"{seconds}s"
        minutes, rest = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}min {rest}s" if rest else f"{minutes}min"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}min" if minutes else f"{hours}h"

    @staticmethod
    def client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR") or None

    @classmethod
    def log_from_request(
        cls,
        request,
        event_type,
        *,
        user=None,
        email="",
        codigo="",
        nome="",
        artista="",
        duration_seconds=0,
        metadata=None,
    ):
        try:
            actor = user if user is not None else getattr(request, "user", None)
            if actor is not None and not getattr(actor, "is_authenticated", False):
                actor = None

            try:
                duration = max(int(float(duration_seconds or 0)), 0)
            except (TypeError, ValueError):
                duration = 0

            return cls.objects.create(
                user=actor,
                event_type=event_type,
                email=email or getattr(actor, "email", "") or "",
                codigo=str(codigo or "").zfill(5) if codigo else "",
                nome=nome or "",
                artista=artista or "",
                duration_seconds=duration,
                path=request.get_full_path()[:500],
                ip_address=cls.client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:300],
                metadata=metadata or {},
            )
        except Exception:
            return None


class SiteConfiguration(models.Model):
    site_name = models.CharField(max_length=120, default="Karaoke do Cowboy")
    hero_subtitle = models.CharField(
        max_length=180,
        default="As 3 mais pedidas do saloon -- bora cantar!",
    )
    allow_registration = models.BooleanField(default=True)
    maintenance_message = models.CharField(max_length=220, blank=True)
    contribution_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    paid_access_hours = models.PositiveIntegerField(default=4)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracao do site"
        verbose_name_plural = "Configuracoes do site"

    def __str__(self):
        return self.site_name

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
