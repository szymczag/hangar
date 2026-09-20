# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations


def remove_unsplash_access_key(apps, schema_editor):
    # Covers are no longer picked from Unsplash: images are only ever this
    # instance's own (docs/content-security-policy.md). A stored access key
    # would be a third-party secret nothing reads.
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    InstanceConfiguration.objects.filter(key="UNSPLASH_ACCESS_KEY").delete()


class Migration(migrations.Migration):
    dependencies = [("license", "0023_openpgp_subject_detail")]
    operations = [migrations.RunPython(remove_unsplash_access_key, migrations.RunPython.noop)]
