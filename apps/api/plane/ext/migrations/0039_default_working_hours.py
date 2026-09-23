# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
OLD_DAY = [{"start": "09:00", "end": "22:00"}]
NEW_DAY = [{"start": "09:00", "end": "17:00"}, {"start": "19:00", "end": "22:00"}]


def _is_untouched_default(schedule):
    if not isinstance(schedule, dict):
        return False
    if any(schedule.get(day) for day in ("sat", "sun")):
        return False
    return all(schedule.get(day) == OLD_DAY for day in WEEKDAYS)


def adopt_the_new_default(apps, schema_editor):
    """Move trainers who never set their hours onto the new default.

    Only those: a profile is rewritten when its schedule is still exactly the old
    default and `schedule_revision` says nobody has ever saved it. Anybody who
    has chosen their hours -- including anybody who chose 09:00-22:00 on purpose
    -- keeps them, because the old value and a deliberate one are the same bytes
    and the revision is the only thing that tells them apart.

    The revision is left alone as well. It counts what the trainer decided, and
    this is Hangar changing its own assumption, not the trainer changing theirs.
    """
    TrainerProfile = apps.get_model("ext", "TrainerProfile")
    for profile in TrainerProfile.objects.filter(schedule_revision=1).iterator():
        if not _is_untouched_default(profile.weekly_schedule):
            continue
        schedule = dict(profile.weekly_schedule)
        for day in WEEKDAYS:
            schedule[day] = [dict(window) for window in NEW_DAY]
        TrainerProfile.objects.filter(pk=profile.pk).update(weekly_schedule=schedule)


def restore_the_old_default(apps, schema_editor):
    TrainerProfile = apps.get_model("ext", "TrainerProfile")
    for profile in TrainerProfile.objects.filter(schedule_revision=1).iterator():
        schedule = profile.weekly_schedule
        if not isinstance(schedule, dict) or any(schedule.get(day) != NEW_DAY for day in WEEKDAYS):
            continue
        restored = dict(schedule)
        for day in WEEKDAYS:
            restored[day] = [dict(window) for window in OLD_DAY]
        TrainerProfile.objects.filter(pk=profile.pk).update(weekly_schedule=restored)


class Migration(migrations.Migration):
    dependencies = [("ext", "0038_workshop_role_properties")]

    operations = [migrations.RunPython(adopt_the_new_default, restore_the_old_default)]
