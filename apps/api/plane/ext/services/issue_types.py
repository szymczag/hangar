# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import transaction

from plane.db.models import Issue, IssueType, Project, Workspace
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

    # Capacity is opt-in. Once a workspace has a trainer profile, keep the
    # canonical Workshop type available in every project without making it the
    # default work item type.
    from plane.ext.models import TrainerProfile

    if TrainerProfile.objects.filter(workspace_id=project.workspace_id).exists():
        ensure_project_workshop_type(project)

    return task_type, epic_type


@transaction.atomic
def ensure_project_workshop_type(project):
    Workspace.objects.select_for_update().get(pk=project.workspace_id)
    workshop, _ = IssueType.objects.get_or_create(
        workspace_id=project.workspace_id,
        system_key=IssueType.SystemKey.WORKSHOP,
        defaults={
            "name": "Workshop",
            "is_epic": False,
            "is_active": True,
            "is_default": False,
            "level": 0,
        },
    )
    IssueType.objects.filter(pk=workshop.pk).update(is_epic=False, is_active=True, is_default=False, level=0)
    workshop.refresh_from_db()
    ProjectIssueType.objects.get_or_create(
        project=project,
        issue_type=workshop,
        defaults={"workspace_id": project.workspace_id, "level": 0, "is_default": False},
    )
    return workshop


def ensure_workspace_workshop_type(workspace):
    workshop = None
    for project in Project.objects.filter(workspace=workspace, archived_at__isnull=True):
        workshop = ensure_project_workshop_type(project)
    return workshop
