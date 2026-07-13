# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


def disable_existing_telemetry(apps, schema_editor):
    instance_model = apps.get_model("license", "Instance")
    instance_model.objects.filter(is_telemetry_enabled=True).update(is_telemetry_enabled=False)


class Migration(migrations.Migration):
    dependencies = [("license", "0006_instance_is_current_version_deprecated")]

    operations = [
        migrations.AlterField(
            model_name="instance",
            name="is_telemetry_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(disable_existing_telemetry, migrations.RunPython.noop),
    ]
