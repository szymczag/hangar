# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0131_google_calendar_workshop_type"),
        ("ext", "0022_workshop_sessions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkshopPlanDraft",
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
                ("title", models.CharField(max_length=255)),
                (
                    "duration_minutes",
                    models.PositiveIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(15),
                            django.core.validators.MaxValueValidator(10080),
                        ]
                    ),
                ),
                (
                    "preparation_minutes",
                    models.PositiveIntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1440),
                        ],
                    ),
                ),
                (
                    "travel_before_minutes",
                    models.PositiveIntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1440),
                        ],
                    ),
                ),
                (
                    "travel_after_minutes",
                    models.PositiveIntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1440),
                        ],
                    ),
                ),
                ("window_starts_at", models.DateTimeField()),
                ("window_ends_at", models.DateTimeField()),
                ("trainer_ids", models.JSONField(default=list)),
                ("revision", models.PositiveBigIntegerField(default=1)),
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
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workshop_plan_drafts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workshop_plan_drafts",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_workshop_plan_drafts",
                "ordering": ("-updated_at", "-created_at"),
                "indexes": [models.Index(fields=["workspace", "owner", "updated_at"], name="ext_plan_draft_owner_idx")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("window_ends_at__gt", models.F("window_starts_at"))),
                        name="ext_plan_draft_valid_window",
                    )
                ],
            },
        ),
        migrations.AlterField(
            model_name="capacityauditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("trainer.activated", "Trainer activated"),
                    ("trainer.suspended", "Trainer suspended"),
                    ("schedule.updated", "Schedule updated"),
                    ("google.connected", "Google connected"),
                    ("google.calendars_updated", "Calendars updated"),
                    ("google.disconnected", "Google disconnected"),
                    ("workshop.updated", "Workshop updated"),
                    ("workshop.removed", "Workshop removed"),
                    ("plan_draft.created", "Plan draft created"),
                    ("plan_draft.updated", "Plan draft updated"),
                    ("plan_draft.removed", "Plan draft removed"),
                ],
                max_length=64,
            ),
        ),
    ]
