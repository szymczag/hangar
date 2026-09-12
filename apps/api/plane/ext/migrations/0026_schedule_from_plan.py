# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Give a plan something to be a plan *for*.

    A draft answered "what has to happen and who could deliver it" and stopped
    there: the hold it produced named a trainer and a time that existed nowhere
    else, and a coordinator retyped both into a Workshop work item by hand. The
    nullable link is what lets the hold be spent instead -- turned into a real
    session on the work item that asked for it.

    Nullable because exploring before there is a work item to attach the answer
    to is a legitimate way to use the planner. Such a draft simply cannot be
    scheduled, which the endpoint says rather than the schema.

    The two `AlterField`s carry no data change. They record new members of
    `CapacityAuditEvent.Action` and `WorkshopPlanHold.Status`, so that a hold
    that became a session is distinguishable in the audit trail from one that
    was let go.
    """

    dependencies = [
        ("db", "0131_google_calendar_workshop_type"),
        ("ext", "0025_drop_plan_draft_window"),
    ]

    operations = [
        migrations.AddField(
            model_name="workshopplandraft",
            name="issue",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="workshop_plan_drafts",
                to="db.issue",
            ),
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
                    ("plan.scheduled", "Plan scheduled"),
                ],
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="workshopplanhold",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("released", "Released"),
                    ("confirmed", "Confirmed"),
                    ("scheduled", "Scheduled"),
                ],
                default="active",
                max_length=16,
            ),
        ),
    ]
