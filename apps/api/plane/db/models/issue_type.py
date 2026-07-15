# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models
from django.db.models import Q

# Module imports
from .project import ProjectBaseModel
from .base import BaseModel


class IssueType(BaseModel):
    class SystemKey(models.TextChoices):
        TASK = "task", "Task"
        EPIC = "epic", "Epic"

    workspace = models.ForeignKey("db.Workspace", related_name="issue_types", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo_props = models.JSONField(default=dict)
    is_epic = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    level = models.FloatField(default=0)
    # Stable system identity is authoritative. The legacy is_epic,
    # is_default, and level columns remain materialized for older consumers;
    # database constraints keep their system-type values synchronized.
    system_key = models.CharField(max_length=32, choices=SystemKey.choices, null=True, blank=True)
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Issue Type"
        verbose_name_plural = "Issue Types"
        db_table = "issue_types"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "system_key"],
                condition=Q(system_key__isnull=False, deleted_at__isnull=True),
                name="issue_type_unique_active_system_key",
            ),
            models.CheckConstraint(
                check=(
                    Q(system_key__isnull=True)
                    | Q(
                        system_key="epic",
                        is_epic=True,
                        is_active=True,
                        is_default=False,
                        level=1,
                    )
                    | Q(
                        system_key="task",
                        is_epic=False,
                        is_active=True,
                        is_default=True,
                        level=0,
                    )
                ),
                name="issue_type_system_key_invariants",
            ),
        ]

    def __str__(self):
        return self.name


class ProjectIssueType(ProjectBaseModel):
    # Project-scoped availability, hierarchy level, and default selection live
    # on this link. System-type provisioning repairs the legacy IssueType
    # mirrors at the same transaction boundary.
    issue_type = models.ForeignKey("db.IssueType", related_name="project_issue_types", on_delete=models.CASCADE)
    level = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ["project", "issue_type", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "issue_type"],
                condition=Q(deleted_at__isnull=True),
                name="project_issue_type_unique_project_issue_type_when_deleted_at_null",
            )
        ]
        verbose_name = "Project Issue Type"
        verbose_name_plural = "Project Issue Types"
        db_table = "project_issue_types"
        ordering = ("project", "issue_type")

    def __str__(self):
        return f"{self.project} - {self.issue_type}"
