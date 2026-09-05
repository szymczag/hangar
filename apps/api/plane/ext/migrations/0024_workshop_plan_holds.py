# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0131_google_calendar_workshop_type"),
        ("ext", "0023_workshop_plan_drafts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkshopPlanHold",
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
                ("workshop_starts_at", models.DateTimeField()),
                ("workshop_ends_at", models.DateTimeField()),
                ("blocked_starts_at", models.DateTimeField()),
                ("blocked_ends_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("released", "Released"), ("confirmed", "Confirmed")],
                        default="active",
                        max_length=16,
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
                    "draft",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="holds",
                        to="ext.workshopplandraft",
                    ),
                ),
                (
                    "trainer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workshop_plan_holds",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workshop_plan_holds",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_workshop_plan_holds",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(
                        fields=["workspace", "trainer", "status", "expires_at"],
                        name="ext_plan_hold_lookup_idx",
                    ),
                    models.Index(fields=["draft", "status"], name="ext_plan_hold_draft_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("workshop_ends_at__gt", models.F("workshop_starts_at"))),
                        name="ext_plan_hold_workshop_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("blocked_ends_at__gt", models.F("blocked_starts_at"))),
                        name="ext_plan_hold_blocked_range",
                    ),
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
                    ("plan_hold.created", "Plan hold created"),
                    ("plan_hold.released", "Plan hold released"),
                ],
                max_length=64,
            ),
        ),
    ]
