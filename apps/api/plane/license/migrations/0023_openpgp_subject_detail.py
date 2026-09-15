# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.db import migrations


def seed_openpgp_subject_detail(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.get_or_create(
        key="OPENPGP_SUBJECT_DETAIL",
        defaults={
            # Off. The generic outer subject is a documented property of
            # encrypted notification mail, so an instance upgrading into this
            # release keeps it until an administrator decides otherwise.
            "value": os.environ.get("OPENPGP_SUBJECT_DETAIL", "0"),
            "category": "SMTP",
            "is_encrypted": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0022_restrict_invites_to_sso_domains")]
    operations = [migrations.RunPython(seed_openpgp_subject_detail, migrations.RunPython.noop)]
