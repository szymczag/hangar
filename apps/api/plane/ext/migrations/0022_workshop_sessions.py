# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill_workshop_sessions(apps, schema_editor):
    WorkshopSchedule = apps.get_model("ext", "WorkshopSchedule")
    WorkshopSession = apps.get_model("ext", "WorkshopSession")
    IssueAssignee = apps.get_model("db", "IssueAssignee")

    for schedule in WorkshopSchedule.objects.filter(deleted_at__isnull=True).iterator():
        session = WorkshopSession.objects.create(
            schedule_id=schedule.id,
            position=0,
            starts_at=schedule.starts_at,
            ends_at=schedule.ends_at,
            preparation_minutes=schedule.preparation_minutes,
            travel_before_minutes=schedule.travel_before_minutes,
            travel_after_minutes=schedule.travel_after_minutes,
        )
        trainer_ids = IssueAssignee.objects.filter(issue_id=schedule.issue_id, deleted_at__isnull=True).values_list(
            "assignee_id", flat=True
        )
        session.trainers.add(*trainer_ids)


class Migration(migrations.Migration):
    dependencies = [
        ("ext", "0021_booking_hours"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkshopSession",
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
                ("position", models.PositiveIntegerField(default=0)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
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
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="ext.workshopschedule",
                    ),
                ),
                (
                    "trainers",
                    models.ManyToManyField(related_name="workshop_sessions", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "db_table": "ext_workshop_sessions",
                "ordering": ("position", "starts_at", "id"),
                "indexes": [models.Index(fields=["starts_at", "ends_at"], name="ext_workshop_session_range_idx")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("ends_at__gt", models.F("starts_at"))),
                        name="ext_workshop_session_valid_range",
                    ),
                    models.UniqueConstraint(fields=("schedule", "position"), name="ext_workshop_session_position"),
                ],
            },
        ),
        migrations.RunPython(backfill_workshop_sessions, migrations.RunPython.noop),
    ]
