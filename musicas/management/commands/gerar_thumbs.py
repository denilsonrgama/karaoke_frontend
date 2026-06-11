import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Gera thumbs .jpg a partir dos videos em MEDIA_ROOT, "
        "salvando como codigo.jpg em musicas/static/media/karaoke."
    )

    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

    def add_arguments(self, parser):
        parser.add_argument(
            "--ss",
            default="00:00:01",
            help="Timestamp para capturar o frame. Ex: 00:00:00.2",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Sobrescreve thumbs existentes.",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Gera somente se nao existir.",
        )
        parser.add_argument(
            "--codigo",
            help="Gera thumb apenas para o arquivo cujo nome comeca com este codigo.",
        )
        parser.add_argument(
            "--video-dir",
            default=str(settings.MEDIA_ROOT),
            help="Pasta dos videos. Padrao: MEDIA_ROOT.",
        )
        parser.add_argument(
            "--output-dir",
            default=str(settings.BASE_DIR / "musicas" / "static" / "media" / "karaoke"),
            help="Pasta de saida das thumbs.",
        )

    def handle(self, *args, **options):
        ss = options["ss"]
        overwrite = options["overwrite"]
        only_missing = options["only_missing"]
        codigo_filtro = options.get("codigo")
        video_dir = Path(options["video_dir"])
        output_dir = Path(options["output_dir"])

        if codigo_filtro and len(codigo_filtro) != 5:
            self.stderr.write(self.style.ERROR("--codigo deve ter exatamente 5 caracteres."))
            return

        if not video_dir.exists():
            self.stderr.write(self.style.ERROR(f"Pasta de videos nao existe: {video_dir}"))
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        videos = [
            path
            for path in video_dir.iterdir()
            if path.is_file() and path.suffix.lower() in self.VIDEO_EXTENSIONS
        ]

        if not videos:
            self.stdout.write(self.style.WARNING("Nenhum video encontrado."))
            return

        ok = skipped = failed = 0

        for video_path in videos:
            codigo = video_path.stem[:5]

            if len(codigo) < 5 or not codigo.isdigit():
                self.stdout.write(
                    self.style.WARNING(f"Ignorado, codigo invalido: {video_path.name}")
                )
                skipped += 1
                continue

            if codigo_filtro and codigo != codigo_filtro:
                continue

            output_file = output_dir / f"{codigo}.jpg"

            if output_file.exists():
                if only_missing:
                    self.stdout.write(f"Ja existe, only-missing: {output_file.name}")
                    skipped += 1
                    continue
                if not overwrite:
                    self.stdout.write(f"Ja existe, use --overwrite: {output_file.name}")
                    skipped += 1
                    continue

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                ss,
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output_file),
            ]

            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Thumb criada: {output_file.name} <- {video_path.name}")
                )
                ok += 1
            except FileNotFoundError:
                self.stderr.write(
                    self.style.ERROR("ffmpeg nao encontrado. Instale e coloque no PATH.")
                )
                return
            except subprocess.CalledProcessError:
                self.stderr.write(self.style.ERROR(f"Erro ao processar: {video_path.name}"))
                failed += 1

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Resumo"))
        self.stdout.write(f"Geradas: {ok}")
        self.stdout.write(f"Puladas: {skipped}")
        self.stdout.write(f"Falhas : {failed}")
