# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


def initialize_recent_usage(apps, _schema_editor):
    ImportAdmissionUsage = apps.get_model("ext", "ImportAdmissionUsage")
    ImportJob = apps.get_model("ext", "ImportJob")
    cutoff = timezone.now() - timedelta(hours=24)
    rows = []
    for job in ImportJob._base_manager.filter(created_at__gt=cutoff).iterator():
        source_rows = job.stats.get("source_rows", 0) if isinstance(job.stats, dict) else 0
        source_rows = source_rows if isinstance(source_rows, int) and source_rows >= 0 else 0
        rows.append(
            ImportAdmissionUsage(
                workspace_id=job.workspace_id,
                user_id=job.initiated_by_id,
                job_id=job.id,
                source_rows=source_rows,
                accepted_at=job.created_at,
            )
        )
    ImportAdmissionUsage._base_manager.bulk_create(rows, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ext", "0009_import_admission_audit"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportAdmissionUsage",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("source_rows", models.PositiveBigIntegerField()),
                ("accepted_at", models.DateTimeField(default=timezone.now)),
                (
                    "job",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admission_usage",
                        to="ext.importjob",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ext_import_admission_usage",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ext_import_admission_usage",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_import_admission_usage",
                "indexes": [
                    models.Index(fields=["workspace", "accepted_at"], name="ext_imp_usage_ws_time_idx"),
                    models.Index(fields=["user", "accepted_at"], name="ext_imp_usage_user_time_idx"),
                ],
            },
        ),
        migrations.RunPython(initialize_recent_usage, migrations.RunPython.noop),
    ]
