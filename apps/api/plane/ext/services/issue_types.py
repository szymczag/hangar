# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import transaction

from plane.db.models import Issue, IssueType, Workspace
from plane.db.models.issue_type import ProjectIssueType


@transaction.atomic
def ensure_project_system_types(project):
    """Provision the canonical Task and Epic types for a project.

    The workspace lock serializes provisioning because system types are shared
    definitions while level/default semantics live on ProjectIssueType.
    """

    Workspace.objects.select_for_update().get(pk=project.workspace_id)

    task_type, _ = IssueType.objects.get_or_create(
        workspace_id=project.workspace_id,
        system_key=IssueType.SystemKey.TASK,
        defaults={
            "name": "Task",
            "is_epic": False,
            "is_active": True,
            "is_default": True,
            "level": 0,
        },
    )
    epic_type, _ = IssueType.objects.get_or_create(
        workspace_id=project.workspace_id,
        system_key=IssueType.SystemKey.EPIC,
        defaults={
            "name": "Epic",
            "is_epic": True,
            "is_active": True,
            "is_default": False,
            "level": 1,
        },
    )

    # Repair drift as well as provisioning missing rows. Display fields remain
    # operator-editable, but system identity and hierarchy semantics do not.
    IssueType.objects.filter(pk=task_type.pk).update(
        is_epic=False,
        is_active=True,
        is_default=True,
        level=0,
    )
    IssueType.objects.filter(pk=epic_type.pk).update(
        is_epic=True,
        is_active=True,
        is_default=False,
        level=1,
    )
    task_type.refresh_from_db()
    epic_type.refresh_from_db()

    task_link, _ = ProjectIssueType.objects.get_or_create(
        project=project,
        issue_type=task_type,
        defaults={"workspace_id": project.workspace_id, "level": 0, "is_default": True},
    )
    epic_link, _ = ProjectIssueType.objects.get_or_create(
        project=project,
        issue_type=epic_type,
        defaults={"workspace_id": project.workspace_id, "level": 1, "is_default": False},
    )

    ProjectIssueType.objects.filter(project=project, is_default=True).exclude(pk=task_link.pk).update(is_default=False)
    ProjectIssueType.objects.filter(pk=task_link.pk).update(level=0, is_default=True)
    ProjectIssueType.objects.filter(pk=epic_link.pk).update(level=1, is_default=False)
    Issue.objects.filter(project=project, type__isnull=True).update(type=task_type)

    return task_type, epic_type
