# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import plane.db.models.issue
import plane.db.models.project


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("db", "0121_alter_estimate_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EpicUserProperty",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
                ),
                ("filters", models.JSONField(default=plane.db.models.issue.get_default_filters)),
                ("display_filters", models.JSONField(default=plane.db.models.issue.get_default_display_filters)),
                ("display_properties", models.JSONField(default=plane.db.models.issue.get_default_display_properties)),
                ("rich_filters", models.JSONField(default=dict)),
                ("preferences", models.JSONField(default=plane.db.models.project.get_default_preferences)),
                ("sort_order", models.FloatField(default=65535)),
                (
                    "created_by",
                    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_created_by", to=settings.AUTH_USER_MODEL, verbose_name="Created By"),
                ),
                (
                    "updated_by",
                    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_updated_by", to=settings.AUTH_USER_MODEL, verbose_name="Last Modified By"),
                ),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_%(class)s", to="db.project"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="epic_user_properties", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "workspace",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_%(class)s", to="db.workspace"),
                ),
            ],
            options={"db_table": "ext_epic_user_properties", "ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="epicuserproperty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("user", "project"),
                name="ext_epic_user_property_unique_active_user_project",
            ),
        ),
    ]
