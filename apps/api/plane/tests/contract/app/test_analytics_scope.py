# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    AnalyticView,
    Cycle,
    CycleIssue,
    Issue,
    Module,
    ModuleIssue,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)


@pytest.fixture
def analytics_scope(db, create_user, workspace):
    unique = uuid4().hex[:8]
    member = User.objects.create(
        email=f"analytics-member-{unique}@example.com",
        username=f"analytics-member-{unique}",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15, is_active=True)

    project = Project.objects.create(
        name="Authorized analytics project",
        identifier=f"A{unique[:4]}",
        workspace=workspace,
        created_by=create_user,
    )
    foreign_project = Project.objects.create(
        name="Guest analytics project",
        identifier=f"G{unique[:4]}",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=member,
        role=15,
        is_active=True,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=foreign_project,
        member=member,
        role=5,
        is_active=True,
    )

    state = State.objects.create(
        name="Started",
        group="started",
        project=foreign_project,
        workspace=workspace,
    )
    issue = Issue.objects.create(
        name="Foreign analytics issue",
        project=foreign_project,
        workspace=workspace,
        state=state,
        created_by=create_user,
    )
    cycle = Cycle.objects.create(
        name="Foreign cycle",
        project=foreign_project,
        workspace=workspace,
        owned_by=create_user,
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(days=7),
    )
    module = Module.objects.create(
        name="Foreign module",
        project=foreign_project,
        workspace=workspace,
    )
    CycleIssue.objects.create(
        issue=issue,
        cycle=cycle,
        project=foreign_project,
        workspace=workspace,
    )
    ModuleIssue.objects.create(
        issue=issue,
        module=module,
        project=foreign_project,
        workspace=workspace,
    )

    client = APIClient()
    client.force_authenticate(user=member)
    return client, project, foreign_project, cycle, module


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["advance-analytics", "advance-analytics-stats"])
@pytest.mark.parametrize("filter_name", ["cycle_id", "module_id"])
def test_advanced_analytics_does_not_cross_project_role_boundary(
    analytics_scope,
    workspace,
    endpoint,
    filter_name,
):
    client, project, _foreign_project, cycle, module = analytics_scope
    foreign_id = cycle.id if filter_name == "cycle_id" else module.id

    response = client.get(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/{endpoint}/",
        {filter_name: str(foreign_id), "type": "work-items"},
    )

    assert response.status_code == status.HTTP_200_OK
    if endpoint == "advance-analytics":
        assert response.data["total_work_items"]["count"] == 0
    else:
        assert list(response.data) == []


@pytest.mark.contract
@pytest.mark.django_db
def test_saved_analytics_is_always_scoped_to_its_workspace(session_client, create_user, workspace):
    foreign_workspace = Workspace.objects.create(
        name="Foreign workspace",
        slug="foreign-analytics-workspace",
        owner=create_user,
    )
    foreign_project = Project.objects.create(
        name="Foreign workspace project",
        identifier="FWP",
        workspace=foreign_workspace,
        created_by=create_user,
    )
    foreign_state = State.objects.create(
        name="Backlog",
        group="backlog",
        project=foreign_project,
        workspace=foreign_workspace,
    )
    Issue.objects.create(
        name="Foreign workspace issue",
        project=foreign_project,
        workspace=foreign_workspace,
        state=foreign_state,
        created_by=create_user,
    )
    analytic = AnalyticView.objects.create(
        workspace=workspace,
        name="Workspace-scoped analytic",
        query={"project_id__in": [str(foreign_project.id)]},
        query_dict={"x_axis": "state__group", "y_axis": "issue_count"},
        created_by=create_user,
    )

    response = session_client.get(f"/api/workspaces/{workspace.slug}/saved-analytic-view/{analytic.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["total"] == 0
    assert response.data["distribution"] == {}


@pytest.mark.contract
@pytest.mark.django_db
def test_global_search_excludes_inactive_workspace_memberships(session_client, workspace, create_user):
    foreign_owner = User.objects.create(
        email="foreign-workspace-owner@example.com",
        username="foreign-workspace-owner",
    )
    revoked_workspace = Workspace.objects.create(
        name="Revoked private workspace",
        slug="revoked-private-workspace",
        owner=foreign_owner,
    )
    WorkspaceMember.objects.create(
        workspace=revoked_workspace,
        member=create_user,
        role=15,
        is_active=False,
    )

    response = session_client.get(
        f"/api/workspaces/{workspace.slug}/search/",
        {"entities": "workspace", "search": "Revoked private"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert list(response.data["results"]["workspace"]) == []
