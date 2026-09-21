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

    # Workshop is deliberately not among the types every project gets. It used to
    # arrive in every project the moment anybody in the workspace became a
    # trainer, which put a training-specific type in the picker of projects that
    # have nothing to do with training. A project now opts in from its own
    # settings -- see `enable_workshops`.
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


def project_workshop_type(project):
    """The Workshop type, if this project offers it; otherwise None. Never adds it."""
    link = (
        ProjectIssueType.objects.filter(
            project=project, issue_type__system_key=IssueType.SystemKey.WORKSHOP, deleted_at__isnull=True
        )
        .select_related("issue_type")
        .first()
    )
    return link.issue_type if link else None


def workshops_enabled(project) -> bool:
    """Whether this project offers the Workshop type.

    The answer is the project's own link to the type, which is already where
    project-scoped availability lives: listing a project's types and validating a
    new work item's type both read it, so a project without the link cannot hold
    a new Workshop by any route, not merely by the one with a picker.
    """
    return ProjectIssueType.objects.filter(
        project=project,
        issue_type__system_key=IssueType.SystemKey.WORKSHOP,
        deleted_at__isnull=True,
    ).exists()


def workshop_count(project) -> int:
    return Issue.objects.filter(project=project, type__system_key=IssueType.SystemKey.WORKSHOP).count()


class WorkshopsInUse(Exception):
    """Raised when a project still holding Workshops is asked to stop offering them."""


@transaction.atomic
def enable_workshops(project):
    """Offer the Workshop type in this project. Idempotent."""
    return ensure_project_workshop_type(project)


@transaction.atomic
def disable_workshops(project):
    """Stop offering the Workshop type here, if nothing in the project is one.

    Refused while Workshops exist, because they would be left as work items of a
    type their own project no longer offers -- editable, but no longer creatable
    alongside, and invisible to anybody reasoning from the picker about what the
    project holds. Moving or retyping them first is a decision for a person.
    """
    if workshop_count(project):
        raise WorkshopsInUse
    ProjectIssueType.objects.filter(
        project=project,
        issue_type__system_key=IssueType.SystemKey.WORKSHOP,
        deleted_at__isnull=True,
    ).delete()
