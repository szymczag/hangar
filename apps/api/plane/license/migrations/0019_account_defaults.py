# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations

# Monday rather than upstream's Sunday, UTC unchanged, and a light theme instead
# of following the operating system. Seeded values only affect accounts created
# after this runs; every existing profile already holds a choice.
DEFAULTS = (
    ("INSTANCE_DEFAULT_START_OF_WEEK", "1"),
    ("INSTANCE_DEFAULT_THEME", "light"),
    ("INSTANCE_DEFAULT_TIMEZONE", "UTC"),
)


def seed_account_defaults(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    for key, fallback in DEFAULTS:
        InstanceConfiguration.objects.get_or_create(
            key=key,
            defaults={
                "value": os.environ.get(key, fallback),
                "category": "PREFERENCES",
                "is_encrypted": False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("license", "0018_external_links")]
    operations = [migrations.RunPython(seed_account_defaults, migrations.RunPython.noop)]
