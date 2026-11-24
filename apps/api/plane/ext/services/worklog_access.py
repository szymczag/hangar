# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who may read worklog data, for the surfaces that list activity of every kind.

Worklogs are confidential from guests (FORK.md, "Security invariants", S20).
The worklog endpoints and the work item activity feed already apply this rule
(`plane/ext/views/worklog.py`, `plane/app/views/issue/activity.py`). A worklog
also writes an `IssueActivity` row with `field="worklog"` and the logged
duration as its value, and that row reaches every other reader of activity: a
user's profile feed and its CSV export, the public API's activity list, and the
notifications sent to the work item's subscribers. Those surfaces use the
helpers here, so the rule is the same everywhere: project admins and members,
and workspace admins, read worklogs; nobody else does.
"""

from django.db.models import Q

from plane.app.permissions import ROLE
from plane.db.models import ProjectMember, WorkspaceMember

WORKLOG_FIELD = "worklog"
WORKLOG_READER_PROJECT_ROLES = (ROLE.ADMIN.value, ROLE.MEMBER.value)


def _is_workspace_admin(user_id, workspace_filter: dict) -> bool:
    return WorkspaceMember.objects.filter(
        member_id=user_id, role=ROLE.ADMIN.value, is_active=True, **workspace_filter
    ).exists()


def worklog_activity_visible_q(user_id, workspace_slug: str) -> Q:
    """Keep worklog activity rows to the projects where `user_id` may read worklogs.

    Every other kind of row passes. Combine it with the surface's own filters; it
    only ever removes rows.
    """
    if _is_workspace_admin(user_id, {"workspace__slug": workspace_slug}):
        return Q()
    reader_projects = ProjectMember.objects.filter(
        workspace__slug=workspace_slug,
        member_id=user_id,
        is_active=True,
        role__in=WORKLOG_READER_PROJECT_ROLES,
    ).values("project_id")
    return ~Q(field=WORKLOG_FIELD) | Q(project_id__in=reader_projects)


def can_read_worklogs(user_id, project_id, workspace_id) -> bool:
    """Whether `user_id` may read the worklogs of one project."""
    if _is_workspace_admin(user_id, {"workspace_id": workspace_id}):
        return True
    return ProjectMember.objects.filter(
        project_id=project_id,
        member_id=user_id,
        is_active=True,
        role__in=WORKLOG_READER_PROJECT_ROLES,
    ).exists()
