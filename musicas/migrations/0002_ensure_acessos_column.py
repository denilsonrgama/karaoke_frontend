from django.db import migrations


def ensure_acessos_column(apps, schema_editor):
    table_name = "musicas_musica"

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    if "acessos" in columns:
        return

    schema_editor.execute(
        "ALTER TABLE musicas_musica "
        "ADD COLUMN acessos integer NOT NULL DEFAULT 0;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("musicas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_acessos_column, migrations.RunPython.noop),
    ]
