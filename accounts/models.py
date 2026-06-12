#accounts/models.py
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


class SiteConfiguration(models.Model):
    site_name = models.CharField(max_length=120, default="Karaoke do Cowboy")
    hero_subtitle = models.CharField(
        max_length=180,
        default="As 3 mais pedidas do saloon -- bora cantar!",
    )
    allow_registration = models.BooleanField(default=True)
    maintenance_message = models.CharField(max_length=220, blank=True)
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
