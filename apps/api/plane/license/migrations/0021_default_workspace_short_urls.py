# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_default_workspace(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="INSTANCE_DEFAULT_WORKSPACE_ID",
        defaults={
            "value": os.environ.get("INSTANCE_DEFAULT_WORKSPACE_ID", ""),
            "category": "WORKSPACE",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0020_support_text")]
    operations = [migrations.RunPython(seed_default_workspace, migrations.RunPython.noop)]
