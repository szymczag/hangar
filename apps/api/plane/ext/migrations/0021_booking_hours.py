# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import migrations, models

import plane.ext.models.capacity


DEFAULT_WORKING_WEEK = {
    "mon": [{"start": "09:00", "end": "22:00"}],
    "tue": [{"start": "09:00", "end": "22:00"}],
    "wed": [{"start": "09:00", "end": "22:00"}],
    "thu": [{"start": "09:00", "end": "22:00"}],
    "fri": [{"start": "09:00", "end": "22:00"}],
    "sat": [],
    "sun": [],
}


def populate_empty_booking_hours(apps, schema_editor):
    TrainerProfile = apps.get_model("ext", "TrainerProfile")
    for profile in TrainerProfile.objects.only("id", "weekly_schedule", "schedule_revision").iterator():
        schedule = profile.weekly_schedule if isinstance(profile.weekly_schedule, dict) else {}
        has_any_interval = any(isinstance(value, list) and len(value) > 0 for value in schedule.values())
        if not has_any_interval:
            profile.weekly_schedule = DEFAULT_WORKING_WEEK
            profile.schedule_revision += 1
            profile.save(update_fields=["weekly_schedule", "schedule_revision"])


class Migration(migrations.Migration):
    dependencies = [("ext", "0020_project_copy_job")]

    operations = [
        migrations.RunPython(populate_empty_booking_hours, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="trainerprofile",
            name="weekly_schedule",
            field=models.JSONField(default=plane.ext.models.capacity.default_working_week),
        ),
        migrations.DeleteModel(name="TrainerScheduleException"),
    ]
