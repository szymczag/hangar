# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone
import django.db.models.deletion


ACTIVE_STATUSES = {"preparing", "queued", "processing", "cancelling"}


def initialize_active_reservations(apps, _schema_editor):
    ImportJob = apps.get_model("ext", "ImportJob")
    ImportUserBudget = apps.get_model("ext", "ImportUserBudget")
    ImportWorkspaceBudget = apps.get_model("ext", "ImportWorkspaceBudget")
    now = timezone.now()
    workspace_usage = {}
    user_usage = {}

    for job in ImportJob._base_manager.filter(status__in=ACTIVE_STATUSES).iterator():
        source_rows = job.stats.get("source_rows", 0) if isinstance(job.stats, dict) else 0
        source_rows = source_rows if isinstance(source_rows, int) and source_rows >= 0 else 0
        workspace = workspace_usage.setdefault(
            job.workspace_id,
            {"active_jobs": 0, "active_source_bytes": 0, "accepted_rows": 0},
        )
        workspace["active_jobs"] += 1
        workspace["active_source_bytes"] += job.source_size
        workspace["accepted_rows"] += source_rows
        if job.initiated_by_id is not None:
            user = user_usage.setdefault(
                (job.workspace_id, job.initiated_by_id),
                {"active_jobs": 0, "accepted_rows": 0},
            )
            user["active_jobs"] += 1
            user["accepted_rows"] += source_rows

    for workspace_id, usage in workspace_usage.items():
        ImportWorkspaceBudget._base_manager.create(
            workspace_id=workspace_id,
            active_jobs=usage["active_jobs"],
            active_source_bytes=usage["active_source_bytes"],
            window_started_at=now,
            accepted_jobs=usage["active_jobs"],
            accepted_rows=usage["accepted_rows"],
        )
    for (workspace_id, user_id), usage in user_usage.items():
        ImportUserBudget._base_manager.create(
            workspace_id=workspace_id,
            user_id=user_id,
            active_jobs=usage["active_jobs"],
            window_started_at=now,
            accepted_jobs=usage["active_jobs"],
            accepted_rows=usage["accepted_rows"],
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ext", "0007_import_job_state_machine"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportWorkspaceBudget",
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
                ("active_jobs", models.PositiveIntegerField(default=0)),
                ("active_source_bytes", models.PositiveBigIntegerField(default=0)),
                ("window_started_at", models.DateTimeField(default=timezone.now)),
                ("accepted_jobs", models.PositiveBigIntegerField(default=0)),
                ("accepted_rows", models.PositiveBigIntegerField(default=0)),
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
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ext_import_budget",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_import_workspace_budgets",
                "constraints": [
                    models.CheckConstraint(
                        check=Q(active_jobs__gte=0),
                        name="ext_imp_ws_budget_jobs_nonnegative",
                    ),
                    models.CheckConstraint(
                        check=Q(active_source_bytes__gte=0),
                        name="ext_imp_ws_budget_bytes_nonnegative",
                    ),
                    models.CheckConstraint(
                        check=Q(accepted_jobs__gte=0, accepted_rows__gte=0),
                        name="ext_imp_ws_budget_usage_nonnegative",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ImportUserBudget",
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
                ("active_jobs", models.PositiveIntegerField(default=0)),
                ("window_started_at", models.DateTimeField(default=timezone.now)),
                ("accepted_jobs", models.PositiveBigIntegerField(default=0)),
                ("accepted_rows", models.PositiveBigIntegerField(default=0)),
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
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ext_import_budgets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ext_import_user_budgets",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_import_user_budgets",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("workspace", "user"),
                        name="ext_imp_user_budget_workspace_user",
                    ),
                    models.CheckConstraint(
                        check=Q(active_jobs__gte=0),
                        name="ext_imp_user_budget_jobs_nonnegative",
                    ),
                    models.CheckConstraint(
                        check=Q(accepted_jobs__gte=0, accepted_rows__gte=0),
                        name="ext_imp_user_budget_usage_nonnegative",
                    ),
                ],
            },
        ),
        migrations.RunPython(initialize_active_reservations, migrations.RunPython.noop),
    ]
