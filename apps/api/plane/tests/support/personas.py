# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A workspace populated so horizontal privilege boundaries can be probed.

The existing authorization probe uses one persona — a member of nothing — which
tests the boundary between tenants. It cannot see the boundaries *inside* a
tenant: a workspace member who was never added to a project, a guest, a project
admin who is not a workspace admin. Those are where an access-control mistake is
most likely to survive review, because every caller in the scenario legitimately
belongs somewhere.

Two projects are essential. With one project, "member of the project" and
"member of the workspace" produce the same answer for every route, so a missing
project-level filter is invisible.

Deliberately not built on plane/tests/factories.py: `WorkspaceMemberFactory` and
`ProjectMemberFactory` both default to `role=20`, so a persona named "guest"
built from them would silently be an administrator and every assertion about it
would pass for the wrong reason.
"""

import uuid
from dataclasses import dataclass, field

from rest_framework.test import APIClient

from plane.db.models import (
    Issue,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)

ROLE_ADMIN = 20
ROLE_MEMBER = 15
ROLE_GUEST = 5


def canary_for(label):
    """A string that exists nowhere but inside one project.

    Its presence in any response is unambiguous evidence of a leak, which is a
    far stronger signal than a status code: several routes legitimately answer
    200 with an empty body to a caller who may not see anything.
    """
    return f"ZZQCANARY{label.upper()}ZZQ"


@dataclass
class ProjectFixture:
    project: Project
    state: State
    issue: Issue
    canary: str


@dataclass
class Scenario:
    workspace: Workspace
    owner: User
    project_a: ProjectFixture
    project_b: ProjectFixture
    other_workspace: Workspace
    other_project: Project
    personas: dict = field(default_factory=dict)

    def client(self, persona):
        client = APIClient()
        client.force_authenticate(user=self.personas[persona])
        return client

    @property
    def canaries(self):
        return (self.project_a.canary, self.project_b.canary)


def _user(prefix):
    return User.objects.create(
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
        is_password_autoset=True,
    )


def _project(workspace, owner, label):
    canary = canary_for(label)
    project = Project.objects.create(
        name=f"Project {label.upper()}",
        identifier=f"{label.upper()}{uuid.uuid4().hex[:3].upper()}",
        workspace=workspace,
        created_by=owner,
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=owner, role=ROLE_ADMIN, is_active=True)
    state = State.objects.create(name="Todo", group="unstarted", workspace=workspace, project=project)
    issue = Issue.objects.create(
        name=canary,
        description_stripped=canary,
        workspace=workspace,
        project=project,
        state=state,
        created_by=owner,
    )
    return ProjectFixture(project=project, state=state, issue=issue, canary=canary)


def build_scenario():
    """One workspace with two projects, one unrelated workspace, seven personas."""
    owner = _user("owner")
    workspace = Workspace.objects.create(
        name="Victim Workspace",
        owner=owner,
        slug=f"victim-{uuid.uuid4().hex[:8]}",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=ROLE_ADMIN, is_active=True)

    project_a = _project(workspace, owner, "a")
    project_b = _project(workspace, owner, "b")

    # A separate tenant, for the cross-workspace persona and for supplying
    # foreign object ids to request bodies.
    other_owner = _user("other-owner")
    other_workspace = Workspace.objects.create(
        name="Other Workspace",
        owner=other_owner,
        slug=f"other-{uuid.uuid4().hex[:8]}",
    )
    WorkspaceMember.objects.create(workspace=other_workspace, member=other_owner, role=ROLE_ADMIN, is_active=True)
    other_project = Project.objects.create(
        name="Other Project",
        identifier=f"OTH{uuid.uuid4().hex[:3].upper()}",
        workspace=other_workspace,
        created_by=other_owner,
    )
    ProjectMember.objects.create(
        workspace=other_workspace,
        project=other_project,
        member=other_owner,
        role=ROLE_ADMIN,
        is_active=True,
    )

    personas = {"owner": owner, "other_owner": other_owner}

    # Belongs to nothing at all.
    personas["outsider"] = _user("outsider")

    # In the workspace, in neither project. The persona the previous probe
    # could not express, and the one that finds a missing project filter.
    ws_member = _user("ws-member")
    WorkspaceMember.objects.create(workspace=workspace, member=ws_member, role=ROLE_MEMBER, is_active=True)
    personas["ws_member_no_project"] = ws_member

    # Guest of project A only.
    guest_a = _user("guest-a")
    WorkspaceMember.objects.create(workspace=workspace, member=guest_a, role=ROLE_GUEST, is_active=True)
    ProjectMember.objects.create(
        workspace=workspace, project=project_a.project, member=guest_a, role=ROLE_GUEST, is_active=True
    )
    personas["guest_a"] = guest_a

    # Full member of project A only — the positive control.
    member_a = _user("member-a")
    WorkspaceMember.objects.create(workspace=workspace, member=member_a, role=ROLE_MEMBER, is_active=True)
    ProjectMember.objects.create(
        workspace=workspace, project=project_a.project, member=member_a, role=ROLE_MEMBER, is_active=True
    )
    personas["member_a"] = member_a

    # Administrator of project A, ordinary member of the workspace.
    admin_a = _user("admin-a")
    WorkspaceMember.objects.create(workspace=workspace, member=admin_a, role=ROLE_MEMBER, is_active=True)
    ProjectMember.objects.create(
        workspace=workspace, project=project_a.project, member=admin_a, role=ROLE_ADMIN, is_active=True
    )
    personas["project_admin_a"] = admin_a

    # Administrator of a different workspace entirely.
    personas["other_workspace_admin"] = other_owner

    # Membership rows exist but the account is deactivated.
    deactivated = _user("deactivated")
    deactivated.is_active = False
    deactivated.save()
    WorkspaceMember.objects.create(workspace=workspace, member=deactivated, role=ROLE_MEMBER, is_active=True)
    ProjectMember.objects.create(
        workspace=workspace, project=project_a.project, member=deactivated, role=ROLE_MEMBER, is_active=True
    )
    personas["deactivated_member"] = deactivated

    return Scenario(
        workspace=workspace,
        owner=owner,
        project_a=project_a,
        project_b=project_b,
        other_workspace=other_workspace,
        other_project=other_project,
        personas=personas,
    )


__all__ = [
    "ROLE_ADMIN",
    "ROLE_GUEST",
    "ROLE_MEMBER",
    "ProjectFixture",
    "Scenario",
    "build_scenario",
    "canary_for",
]
