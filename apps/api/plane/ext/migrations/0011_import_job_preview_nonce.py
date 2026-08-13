# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ext", "0010_import_admission_usage")]

    operations = [
        migrations.AddField(
            model_name="importjob",
            name="preview_nonce",
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
