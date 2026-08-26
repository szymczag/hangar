# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations

BRANDING_KEYS = (
    "INSTANCE_BRANDING_NAME",
    "INSTANCE_SIGN_IN_HEADER",
    "INSTANCE_SIGN_IN_SUBHEADER",
    "INSTANCE_LOGO_ASSET_ID",
)


def seed_branding(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    for key in BRANDING_KEYS:
        InstanceConfiguration.objects.get_or_create(
            key=key,
            defaults={
                # Empty means "use the built-in wording and wordmark", so an
                # instance that never touches these looks exactly as before.
                "value": os.environ.get(key, ""),
                "category": "BRANDING",
                "is_encrypted": False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("license", "0013_api_token_minimum_role")]
    operations = [migrations.RunPython(seed_branding, migrations.RunPython.noop)]
