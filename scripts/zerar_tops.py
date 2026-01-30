from django.core.management.base import BaseCommand
from musicas.models import Musica

class Command(BaseCommand):
    help = "Zera a contagem de acessos (Top 3)"

    def handle(self, *args, **options):
        total = Musica.objects.update(acessos=0)
        self.stdout.write(self.style.SUCCESS(
            f"{total} músicas tiveram os acessos zerados."
        ))
