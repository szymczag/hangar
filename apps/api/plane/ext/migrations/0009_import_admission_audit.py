# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ext", "0008_import_admission_budgets"),
    ]

    operations = [
        migrations.AlterField(
            model_name="importauditevent",
            name="job_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
