# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_api_token_minimum_role(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="API_TOKEN_MINIMUM_ROLE",
        defaults={
            # Guest: what every workspace member could already do, so upgrading
            # does not take anyone's ability to mint a token away silently.
            "value": os.environ.get("API_TOKEN_MINIMUM_ROLE", "5"),
            "category": "WORKSPACE_MANAGEMENT",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0012_sso_auto_join_projects")]
    operations = [migrations.RunPython(seed_api_token_minimum_role, migrations.RunPython.noop)]
