# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for the workspace-role guard on ``ProjectInvitationsViewset.create``.

The guard read ``.role`` off the queryset rather than off a member, so every
call raised ``AttributeError`` before an invitation was ever created — the
endpoint answered 500 for admins and guests alike. With the queryset evaluated,
the guard itself also has to hold: a workspace guest or admin keeps that role in
every project, so a project invite may not hand them a different one.
"""

from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Project, ProjectMember, ProjectMemberInvite, User, WorkspaceMember


def _invites_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/invitations/"


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Invite Project", identifier="INV", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20, is_active=True)
    return project


def _workspace_user(workspace, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"member-{uid}@plane.so", username=f"member_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    return user


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectInviteRoleCheck:
    def test_inviting_a_workspace_member_does_not_error(self, session_client, workspace, project):
        """The regression: this raised AttributeError -> 500 for every payload."""
        member = _workspace_user(workspace, role=15)
        response = session_client.post(
            _invites_url(workspace.slug, project.id),
            {"emails": [{"email": member.email, "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert ProjectMemberInvite.objects.filter(project=project, email=member.email).exists()

    def test_workspace_guest_cannot_be_invited_as_project_member(self, session_client, workspace, project):
        guest = _workspace_user(workspace, role=5)
        response = session_client.post(
            _invites_url(workspace.slug, project.id),
            {"emails": [{"email": guest.email, "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert not ProjectMemberInvite.objects.filter(project=project, email=guest.email).exists()

    def test_workspace_guest_may_be_invited_as_a_guest(self, session_client, workspace, project):
        guest = _workspace_user(workspace, role=5)
        response = session_client.post(
            _invites_url(workspace.slug, project.id),
            {"emails": [{"email": guest.email, "role": 5}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_role_sent_as_a_string_is_compared_as_a_number(self, session_client, workspace, project):
        """JSON clients send "5" as often as 5; the guard must not be bypassed by the type."""
        guest = _workspace_user(workspace, role=5)
        response = session_client.post(
            _invites_url(workspace.slug, project.id),
            {"emails": [{"email": guest.email, "role": "15"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_unparseable_role_is_refused_rather_than_crashing(self, session_client, workspace, project):
        guest = _workspace_user(workspace, role=5)
        response = session_client.post(
            _invites_url(workspace.slug, project.id),
            {"emails": [{"email": guest.email, "role": "admin"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_non_member_is_not_measured_against_a_workspace_role(self, session_client, workspace, project):
        """An address with no workspace membership has no role to contradict."""
        response = session_client.post(
            _invites_url(workspace.slug, project.id),
            {"emails": [{"email": "outsider@plane.so", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
