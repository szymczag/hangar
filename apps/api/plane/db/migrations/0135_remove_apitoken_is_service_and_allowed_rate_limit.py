# Ported from makeplane/plane#10032, where it is 0123; renumbered onto Hangar's chain.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0134_reset_project_deploy_board_identity"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="apitoken",
            name="is_service",
        ),
        migrations.RemoveField(
            model_name="apitoken",
            name="allowed_rate_limit",
        ),
    ]
