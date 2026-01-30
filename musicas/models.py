from django.db import models
from django.db import models


class Musica(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=200)
    artista = models.CharField(max_length=200)

    acessos = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-acessos"]

    def __str__(self):
        return f"{self.nome} - {self.artista}"

    def incrementar_acesso(self):
        self.acessos += 1
        self.save(update_fields=["acessos"])
