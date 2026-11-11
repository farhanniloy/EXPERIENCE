from django.db import connection, migrations


def enable_btree_gist(apps, schema_editor):
    if connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunPython(enable_btree_gist, reverse_code=migrations.RunPython.noop),
    ]
