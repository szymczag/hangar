# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0125_todoist_import_idempotency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="issue",
            name="external_id",
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="issue",
            name="external_source",
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="issuecomment",
            name="external_id",
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="issuecomment",
            name="external_source",
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
    ]
