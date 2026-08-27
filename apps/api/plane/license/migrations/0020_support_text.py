# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_support_text(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="INSTANCE_SUPPORT_TEXT",
        defaults={
            "value": os.environ.get("INSTANCE_SUPPORT_TEXT", ""),
            "category": "BRANDING",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0019_account_defaults")]
    operations = [migrations.RunPython(seed_support_text, migrations.RunPython.noop)]
