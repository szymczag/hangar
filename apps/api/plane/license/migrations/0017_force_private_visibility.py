# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_force_private_visibility(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="FORCE_PRIVATE_VISIBILITY",
        defaults={
            "value": os.environ.get("FORCE_PRIVATE_VISIBILITY", "0"),
            "category": "VISIBILITY",
            "is_encrypted": False,
        },
    )


def apply_to_existing_objects(apps, schema_editor):
    """Only where the deployment asked for it before this ever ran.

    Seeded from the environment above, so an instance that set
    FORCE_PRIVATE_VISIBILITY=1 gets its existing content brought into line as
    part of the upgrade rather than after somebody notices. An instance that did
    not is untouched: this must not decide on its own that content someone chose
    to publish should stop being readable.
    """
    if os.environ.get("FORCE_PRIVATE_VISIBILITY", "0") != "1":
        return

    from plane.utils.visibility_policy import apply_private_visibility

    apply_private_visibility(apps=apps)


class Migration(migrations.Migration):
    dependencies = [
        ("license", "0016_google_auto_redirect"),
        ("db", "0129_alter_draftissue_assignees_alter_issue_assignees_and_more"),
    ]
    operations = [
        migrations.RunPython(seed_force_private_visibility, migrations.RunPython.noop),
        migrations.RunPython(apply_to_existing_objects, migrations.RunPython.noop),
    ]
