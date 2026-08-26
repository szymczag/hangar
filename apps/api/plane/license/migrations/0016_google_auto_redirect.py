# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_google_auto_redirect(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="GOOGLE_AUTO_REDIRECT",
        defaults={
            "value": os.environ.get("GOOGLE_AUTO_REDIRECT", "0"),
            "category": "GOOGLE",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0015_login_page_appearance")]
    operations = [migrations.RunPython(seed_google_auto_redirect, migrations.RunPython.noop)]
