# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regression cover for unauthorized view creation.

Both view viewsets decorated every action except ``create``, which was left on
the unguarded ``ModelViewSet`` default. Any authenticated user could therefore
POST a view into a workspace or project they had no membership in, and because
the record is created with ``access=1`` it then appeared in the real members'
view list — content injected into someone else's UI by a stranger.

This matters most for an instance that federates signup: a person who signs in
through SSO and is deliberately left out of every workspace still held an
account, and that was enough.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import IssueView, Project, ProjectMember, User, Workspace, WorkspaceMember


@pytest.fixture
def victim(db):
    owner = User.objects.create(email=f"owner-{uuid.uuid4().hex[:8]}@example.com", username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(name="Victim", owner=owner, slug=f"victim-{uuid.uuid4().hex[:8]}")
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    project = Project.objects.create(
        name="Victim Project",
        identifier=f"V{uuid.uuid4().hex[:4]}".upper(),
        workspace=workspace,
        created_by=owner,
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=owner, role=20, is_active=True)
    return workspace, project, owner


@pytest.fixture
def outsider_client(db):
    outsider = User.objects.create(
        email=f"outsider-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
    )
    client = APIClient()
    client.force_authenticate(user=outsider)
    return client


PAYLOAD = {"name": "ATTACKER-VIEW", "filters": {}, "access": 1}


@pytest.mark.contract
@pytest.mark.django_db
def test_non_member_cannot_create_a_project_view(victim, outsider_client):
    workspace, project, _owner = victim

    response = outsider_client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/views/",
        PAYLOAD,
        format="json",
    )

    assert response.status_code == 403, response.content
    assert not IssueView.objects.filter(name="ATTACKER-VIEW").exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_non_member_cannot_create_a_workspace_view(victim, outsider_client):
    workspace, _project, _owner = victim

    response = outsider_client.post(
        f"/api/workspaces/{workspace.slug}/views/",
        PAYLOAD,
        format="json",
    )

    assert response.status_code == 403, response.content
    assert not IssueView.objects.filter(name="ATTACKER-VIEW").exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_member_can_still_create_views(victim):
    """The fix must not cost members the ability to create views."""
    workspace, project, owner = victim
    client = APIClient()
    client.force_authenticate(user=owner)

    project_view = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/views/",
        {"name": "Member project view", "filters": {}, "access": 1},
        format="json",
    )
    workspace_view = client.post(
        f"/api/workspaces/{workspace.slug}/views/",
        {"name": "Member workspace view", "filters": {}, "access": 1},
        format="json",
    )

    assert project_view.status_code == 201, project_view.content
    assert workspace_view.status_code == 201, workspace_view.content
    assert IssueView.objects.filter(name="Member project view", project=project).exists()
    assert IssueView.objects.filter(name="Member workspace view", project__isnull=True).exists()
