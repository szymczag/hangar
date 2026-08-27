# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_show_external_links(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="INSTANCE_SHOW_EXTERNAL_LINKS",
        defaults={
            "value": os.environ.get("INSTANCE_SHOW_EXTERNAL_LINKS", "0"),
            "category": "BRANDING",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0017_force_private_visibility")]
    operations = [migrations.RunPython(seed_show_external_links, migrations.RunPython.noop)]
