# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ext", "0018_capacity_audit_events")]

    operations = [
        migrations.AddField(
            model_name="trainerprofile",
            name="schedule_revision",
            field=models.PositiveBigIntegerField(default=1),
        )
    ]
