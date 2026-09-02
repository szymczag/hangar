# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ext", "0017_google_calendar_capacity")]

    operations = [
        migrations.CreateModel(
            name="CapacityAuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("workspace_id", models.UUIDField(db_index=True)),
                ("actor_id", models.UUIDField(db_index=True)),
                ("trainer_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("issue_id", models.UUIDField(blank=True, db_index=True, null=True)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("trainer.activated", "Trainer activated"),
                            ("trainer.suspended", "Trainer suspended"),
                            ("schedule.updated", "Schedule updated"),
                            ("google.connected", "Google connected"),
                            ("google.calendars_updated", "Calendars updated"),
                            ("google.disconnected", "Google disconnected"),
                            ("workshop.updated", "Workshop updated"),
                            ("workshop.removed", "Workshop removed"),
                        ],
                        max_length=64,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ext_capacity_audit_events",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["workspace_id", "created_at"], name="ext_cap_audit_ws_time_idx")
                ],
            },
        )
    ]
