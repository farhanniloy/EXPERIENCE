import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0006_alter_user_managers_remove_user_groups_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="auth_user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="along_account",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
