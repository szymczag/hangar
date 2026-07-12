# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import models

from plane.db.models.issue import get_default_display_filters, get_default_display_properties, get_default_filters
from plane.db.models.project import ProjectBaseModel, get_default_preferences


class EpicUserProperty(ProjectBaseModel):
    """Per-user Epic filters, kept separate from ordinary work-item preferences."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="epic_user_properties")
    filters = models.JSONField(default=get_default_filters)
    display_filters = models.JSONField(default=get_default_display_filters)
    display_properties = models.JSONField(default=get_default_display_properties)
    rich_filters = models.JSONField(default=dict)
    preferences = models.JSONField(default=get_default_preferences)
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "ext_epic_user_properties"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project"],
                condition=models.Q(deleted_at__isnull=True),
                name="ext_epic_user_property_unique_active_user_project",
            )
        ]
