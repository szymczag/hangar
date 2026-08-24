# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_sso_auto_join_projects(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="SSO_AUTO_JOIN_PROJECTS",
        defaults={
            "value": os.environ.get("SSO_AUTO_JOIN_PROJECTS", ""),
            "category": "SSO",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0011_sso_auto_join_workspaces")]
    operations = [migrations.RunPython(seed_sso_auto_join_projects, migrations.RunPython.noop)]
