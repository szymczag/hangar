# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0121_alter_estimate_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ext", "0005_runner_foundation_hardening"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportJob",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[("todoist_csv", "Todoist CSV")], default="todoist_csv", max_length=32
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("completed_with_errors", "Completed with errors"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("source_key", models.TextField(blank=True)),
                ("source_digest", models.CharField(max_length=64)),
                ("source_size", models.PositiveBigIntegerField(default=0)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("reason", models.CharField(blank=True, max_length=100)),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_requested_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("source_deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "initiated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ext_import_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ext_import_jobs",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ext_import_jobs",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Import Job",
                "verbose_name_plural": "Import Jobs",
                "db_table": "ext_import_jobs",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["workspace", "created_at"], name="ext_imp_ws_created_idx"),
                    models.Index(fields=["workspace", "status"], name="ext_imp_ws_status_idx"),
                    models.Index(fields=["project", "source_digest"], name="ext_imp_project_hash_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["queued", "processing"])),
                fields=("project",),
                name="ext_imp_one_active_per_project",
            ),
        ),
    ]
