# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_allow_members_to_invite(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="ALLOW_MEMBERS_TO_INVITE",
        defaults={
            # Off: only workspace admins invite until an operator hands it to
            # members. Members could invite before this existed; that was the
            # gap this setting closes, so the upgrade closes it too.
            "value": os.environ.get("ALLOW_MEMBERS_TO_INVITE", "0"),
            "category": "WORKSPACE_MANAGEMENT",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0024_remove_unsplash_access_key")]
    operations = [migrations.RunPython(seed_allow_members_to_invite, migrations.RunPython.noop)]
