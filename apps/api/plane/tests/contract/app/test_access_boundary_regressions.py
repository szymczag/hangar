# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Cycle,
    DeployBoard,
    Issue,
    Module,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)


@pytest.fixture
def access_boundaries(db, workspace, create_user):
    project = Project.objects.create(
        name="Access boundary project",
        identifier=f"B{uuid4().hex[:4]}",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    cycle = Cycle.objects.create(
        name="Protected cycle",
        workspace=workspace,
        project=project,
        owned_by=create_user,
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(days=7),
    )
    module = Module.objects.create(
        name="Protected module",
        workspace=workspace,
        project=project,
    )
    state = State.objects.create(
        name="Todo",
        group="unstarted",
        workspace=workspace,
        project=project,
    )
    issue = Issue.objects.create(
        name="Published issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=create_user,
    )
    disabled_board = DeployBoard.objects.create(
        workspace=workspace,
        project=project,
        entity_name="project",
        entity_identifier=project.id,
        is_disabled=True,
    )
    return project, cycle, module, issue, disabled_board


@pytest.mark.contract
@pytest.mark.django_db
def test_guest_cannot_put_cycle(access_boundaries, workspace):
    project, cycle, _module, _issue, _board = access_boundaries
    unique = uuid4().hex[:8]
    guest = User.objects.create(
        email=f"cycle-guest-{unique}@example.com",
        username=f"cycle-guest-{unique}",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=guest,
        role=5,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=guest)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/cycles/{cycle.id}/",
        {"name": "Guest changed cycle"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    cycle.refresh_from_db()
    assert cycle.name == "Protected cycle"


@pytest.mark.contract
@pytest.mark.django_db
def test_non_member_cannot_put_module(access_boundaries, workspace):
    project, _cycle, module, _issue, _board = access_boundaries
    unique = uuid4().hex[:8]
    outsider = User.objects.create(
        email=f"module-outsider-{unique}@example.com",
        username=f"module-outsider-{unique}",
    )
    client = APIClient()
    client.force_authenticate(user=outsider)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/modules/{module.id}/",
        {"name": "Outsider changed module"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    module.refresh_from_db()
    assert module.name == "Protected module"


@pytest.mark.contract
@pytest.mark.django_db
def test_disabled_project_board_hides_issue_list_and_detail(access_boundaries):
    _project, _cycle, _module, issue, board = access_boundaries
    client = APIClient()

    list_response = client.get(f"/api/public/anchor/{board.anchor}/issues/")
    detail_response = client.get(f"/api/public/anchor/{board.anchor}/issues/{issue.id}/")

    assert list_response.status_code == status.HTTP_404_NOT_FOUND
    assert detail_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
@pytest.mark.django_db
def test_non_project_board_cannot_expose_project_issue_routes(access_boundaries):
    project, cycle, _module, issue, _disabled_board = access_boundaries
    cycle_board = DeployBoard.objects.create(
        workspace=project.workspace,
        project=project,
        entity_name="cycle",
        entity_identifier=cycle.id,
        is_disabled=False,
    )
    client = APIClient()

    list_response = client.get(f"/api/public/anchor/{cycle_board.anchor}/issues/")
    detail_response = client.get(f"/api/public/anchor/{cycle_board.anchor}/issues/{issue.id}/")

    assert list_response.status_code == status.HTTP_404_NOT_FOUND
    assert detail_response.status_code == status.HTTP_404_NOT_FOUND
