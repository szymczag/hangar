# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0131_google_calendar_workshop_type")]

    operations = [
        migrations.AddField(
            model_name="emailnotificationlog",
            name="attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="emailnotificationlog",
            name="last_error",
            field=models.TextField(blank=True, default=""),
        ),
    ]
