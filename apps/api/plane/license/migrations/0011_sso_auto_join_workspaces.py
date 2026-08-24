# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_sso_auto_join(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="SSO_AUTO_JOIN_WORKSPACES",
        defaults={
            "value": os.environ.get("SSO_AUTO_JOIN_WORKSPACES", ""),
            "category": "SSO",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0010_sso_enforced_domains")]
    operations = [migrations.RunPython(seed_sso_auto_join, migrations.RunPython.noop)]
