# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import timedelta

from django.db import migrations, models
from django.db.models import F


def restore_windows(apps, schema_editor):
    """
    Give every draft a window again, on the way back to rc.51.

    Only ever runs in reverse. The columns are re-added nullable, so without this
    the `NOT NULL` that follows fails on the first existing draft -- which is any
    instance where a coordinator has saved a plan. There is nothing to restore
    them *to*, the information having been deliberately discarded, so each draft
    is given the fortnight beginning when it was created: the shape rc.51 wrote
    for a plan saved that day, valid under the check constraint that comes back
    with it. A draft older than that opens on a window in the past, which rc.51
    handles the same way it handles any stale draft -- the coordinator steps the
    week and saves.
    """
    drafts = apps.get_model("ext", "WorkshopPlanDraft")
    drafts.objects.update(window_starts_at=F("created_at"), window_ends_at=F("created_at") + timedelta(days=14))


class Migration(migrations.Migration):
    """
    The planning window was never part of the plan.

    A draft answers "what has to happen, how long does it take, and who could
    deliver it". Which fortnight the coordinator happened to be looking at when
    they saved it is view state -- it already lives in the planner's `?week=`
    parameter -- and storing it here made every step of the week dirty the draft,
    which in turn collided with the rule that a held plan may not be edited.

    Holds are validated against the trainer's real availability and the existing
    conflict checks, not against these columns, so nothing downstream needs them.

    The operations are ordered for the way back as much as for the way forward:
    reversed, they re-add the columns nullable, refill them, and only then
    reimpose `NOT NULL` and the constraint over them.
    """

    dependencies = [("ext", "0024_workshop_plan_holds")]

    operations = [
        migrations.RemoveConstraint(
            model_name="workshopplandraft",
            name="ext_plan_draft_valid_window",
        ),
        migrations.AlterField(
            model_name="workshopplandraft",
            name="window_starts_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name="workshopplandraft",
            name="window_ends_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(migrations.RunPython.noop, restore_windows),
        migrations.RemoveField(model_name="workshopplandraft", name="window_starts_at"),
        migrations.RemoveField(model_name="workshopplandraft", name="window_ends_at"),
    ]
