# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_sso_enforced_domains(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="SSO_ENFORCED_DOMAINS",
        defaults={
            "value": os.environ.get("SSO_ENFORCED_DOMAINS", ""),
            "category": "SSO",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0009_remove_mutable_posthog_host")]
    operations = [migrations.RunPython(seed_sso_enforced_domains, migrations.RunPython.noop)]
