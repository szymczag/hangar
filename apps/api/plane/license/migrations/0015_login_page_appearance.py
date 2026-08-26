# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations

APPEARANCE_KEYS = {
    "INSTANCE_LOGIN_BACKGROUND_ASSET_ID": "",
    "INSTANCE_ACCENT_COLOR": "",
    "INSTANCE_LOGIN_BACKDROP_COLOR": "",
    # On by default: the AGPL source offer is a licence obligation, so an
    # upgrade must not quietly stop making it.
    "INSTANCE_SHOW_LICENSE_NOTICE": "1",
}


def seed_login_appearance(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    for key, fallback in APPEARANCE_KEYS.items():
        InstanceConfiguration.objects.get_or_create(
            key=key,
            defaults={
                "value": os.environ.get(key, fallback),
                "category": "BRANDING",
                "is_encrypted": False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("license", "0014_instance_branding")]
    operations = [migrations.RunPython(seed_login_appearance, migrations.RunPython.noop)]
