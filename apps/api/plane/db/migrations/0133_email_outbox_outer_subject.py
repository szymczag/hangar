# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0132_email_notification_log_attempts")]

    operations = [
        migrations.AddField(
            model_name="emailoutbox",
            name="outer_subject",
            field=models.CharField(blank=True, default="", max_length=998),
        )
    ]
