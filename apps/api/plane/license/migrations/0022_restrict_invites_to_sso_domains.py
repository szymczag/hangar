# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_restrict_invites(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="RESTRICT_INVITES_TO_SSO_DOMAINS",
        defaults={
            # Off, so an instance that invites addresses outside its pinned
            # domains keeps doing so until an admin decides otherwise.
            "value": os.environ.get("RESTRICT_INVITES_TO_SSO_DOMAINS", "0"),
            "category": "SSO",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0021_default_workspace_short_urls")]
    operations = [migrations.RunPython(seed_restrict_invites, migrations.RunPython.noop)]
