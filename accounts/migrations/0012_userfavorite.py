from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_auditevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserFavorite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=20)),
                ("nome", models.CharField(blank=True, max_length=200)),
                ("artista", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorite_songs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Musica favorita",
                "verbose_name_plural": "Musicas favoritas",
                "ordering": ["-created_at"],
                "unique_together": {("user", "codigo")},
            },
        ),
        migrations.AddIndex(
            model_name="userfavorite",
            index=models.Index(fields=["user", "-created_at"], name="accounts_us_user_id_720df0_idx"),
        ),
        migrations.AddIndex(
            model_name="userfavorite",
            index=models.Index(fields=["codigo"], name="accounts_us_codigo_912bae_idx"),
        ),
    ]
