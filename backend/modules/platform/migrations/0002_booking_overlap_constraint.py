from django.db import migrations


def add_booking_overlap_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE platform_booking
            ADD CONSTRAINT no_overlapping_active_bookings
            EXCLUDE USING gist (
                host_id WITH =,
                tstzrange(start_at, end_at, '[)') WITH &&
            )
            WHERE (status IN ('awaiting_payment', 'confirmed', 'in_progress'));
            """
        )


def remove_booking_overlap_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE platform_booking DROP CONSTRAINT IF EXISTS no_overlapping_active_bookings;"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("infrastructure", "0001_enable_btree_gist"),
        ("platform", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_booking_overlap_constraint, remove_booking_overlap_constraint),
    ]
