# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import connection

from plane.db.models import Issue
from plane.db.models.issue_type import ProjectIssueType

MAX_HIERARCHY_DEPTH = 100


class WorkItemInvariantError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def parent_ancestry_ids(*, parent_id, project_id, workspace_id):
    """Return a bounded parent chain in one parameterized database query."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE ancestry AS (
                SELECT
                    issue.id,
                    issue.parent_id,
                    ARRAY[issue.id] AS path,
                    FALSE AS cycle,
                    1 AS depth
                FROM issues AS issue
                WHERE issue.id = %s
                  AND issue.project_id = %s
                  AND issue.workspace_id = %s
                  AND issue.deleted_at IS NULL

                UNION ALL

                SELECT
                    parent.id,
                    parent.parent_id,
                    ancestry.path || parent.id,
                    parent.id = ANY(ancestry.path) AS cycle,
                    ancestry.depth + 1 AS depth
                FROM issues AS parent
                INNER JOIN ancestry ON parent.id = ancestry.parent_id
                WHERE parent.project_id = %s
                  AND parent.workspace_id = %s
                  AND parent.deleted_at IS NULL
                  AND NOT ancestry.cycle
                  AND ancestry.depth < %s
            )
            SELECT
                ancestry.id,
                ancestry.parent_id,
                ancestry.cycle,
                ancestry.depth,
                EXISTS (
                    SELECT 1
                    FROM issues AS next_parent
                    WHERE next_parent.id = ancestry.parent_id
                      AND next_parent.project_id = %s
                      AND next_parent.workspace_id = %s
                      AND next_parent.deleted_at IS NULL
                ) AS has_parent
            FROM ancestry
            ORDER BY ancestry.depth
            """,
            [
                parent_id,
                project_id,
                workspace_id,
                project_id,
                workspace_id,
                MAX_HIERARCHY_DEPTH,
                project_id,
                workspace_id,
            ],
        )
        rows = cursor.fetchall()

    if any(row[2] for row in rows):
        raise WorkItemInvariantError("parent_id", "The existing parent hierarchy contains a cycle")
    if rows and rows[-1][3] == MAX_HIERARCHY_DEPTH and rows[-1][4]:
        raise WorkItemInvariantError(
            "parent_id",
            f"Work item hierarchy cannot exceed {MAX_HIERARCHY_DEPTH} levels",
        )
    return {row[0] for row in rows}


def project_default_issue_type(project_id):
    link = (
        ProjectIssueType.objects.filter(
            project_id=project_id,
            is_default=True,
            issue_type__is_active=True,
        )
        .select_related("issue_type")
        .first()
    )
    if link:
        return link.issue_type

    from plane.db.models import Project
    from plane.ext.services.issue_types import ensure_project_system_types

    project = Project.objects.get(pk=project_id)
    task_type, _ = ensure_project_system_types(project)
    return task_type


def validate_work_item_assignment(*, project_id, workspace_id, issue_type, parent, issue_id=None):
    """Validate and canonicalize type/parent assignment for every API surface."""

    if issue_type is not None and (
        not issue_type.is_active
        or not ProjectIssueType.objects.filter(
            project_id=project_id,
            issue_type=issue_type,
        ).exists()
    ):
        raise WorkItemInvariantError("type_id", "Work item type is not active for this project")

    scoped_parent = None
    if parent is not None:
        scoped_parent = (
            Issue.objects.filter(
                pk=parent.pk,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            .only("id", "parent_id")
            .first()
        )
        if scoped_parent is None:
            raise WorkItemInvariantError("parent_id", "Parent must belong to this project")

    if issue_type is not None and issue_type.is_epic and scoped_parent is not None:
        raise WorkItemInvariantError("parent_id", "Epic work items cannot have a parent")

    if scoped_parent is None:
        return scoped_parent

    ancestry_ids = parent_ancestry_ids(
        parent_id=scoped_parent.id,
        project_id=project_id,
        workspace_id=workspace_id,
    )
    if issue_id is not None and issue_id in ancestry_ids:
        raise WorkItemInvariantError("parent_id", "Parent assignment would create a cycle")
    return scoped_parent
