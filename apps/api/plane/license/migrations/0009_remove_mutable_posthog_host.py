# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations


def remove_mutable_posthog_host(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.filter(key="POSTHOG_HOST").delete()


class Migration(migrations.Migration):
    dependencies = [("license", "0008_secure_sso_configuration")]
    operations = [
        migrations.RunPython(
            remove_mutable_posthog_host,
            migrations.RunPython.noop,
        )
    ]
