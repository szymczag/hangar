# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""``IntakeIssueViewSet`` on a project without a usable intake: create refuses before
writing anything, and the detail routes answer 404 instead of 500."""

import pytest
from rest_framework import status

from plane.celery import app as celery_app
from plane.db.models import Intake, IntakeIssue, Issue, Project, ProjectMember, State


@pytest.fixture(autouse=True)
def celery_eager():
    """Run the issue activity task in-process; there is no broker in the test stack."""
    original_always_eager = celery_app.conf.task_always_eager
    original_eager_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    yield
    celery_app.conf.task_always_eager = original_always_eager
    celery_app.conf.task_eager_propagates = original_eager_propagates


def make_project(workspace, user, intake_view):
    project = Project.objects.create(
        name="Intake Project", identifier="IP", workspace=workspace, created_by=user, intake_view=intake_view
    )
    ProjectMember.objects.create(project=project, member=user, role=20, is_active=True)
    State.objects.create(
        name="Triage", color="#000000", group="triage", default=True, project=project, workspace=workspace
    )
    return project


def list_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/intake-issues/"


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("intake_view", [False, True])
def test_create_without_intake_row_is_refused_and_writes_nothing(session_client, workspace, create_user, intake_view):
    project = make_project(workspace, create_user, intake_view=intake_view)
    issues_before = Issue.all_objects.filter(project=project).count()

    response = session_client.post(list_url(workspace, project), {"issue": {"name": "x"}}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
    assert Issue.all_objects.filter(project=project).count() == issues_before
    assert not IntakeIssue.all_objects.filter(project=project).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_create_with_intake_turned_off_is_refused_and_writes_nothing(session_client, workspace, create_user):
    project = make_project(workspace, create_user, intake_view=False)
    Intake.objects.create(name="Intake", project=project, workspace=workspace, is_default=True)
    issues_before = Issue.all_objects.filter(project=project).count()

    response = session_client.post(list_url(workspace, project), {"issue": {"name": "x"}}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
    assert Issue.all_objects.filter(project=project).count() == issues_before
    assert not IntakeIssue.all_objects.filter(project=project).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_create_with_intake_enabled_still_works(session_client, workspace, create_user):
    project = make_project(workspace, create_user, intake_view=True)
    intake = Intake.objects.create(name="Intake", project=project, workspace=workspace, is_default=True)

    response = session_client.post(list_url(workspace, project), {"issue": {"name": "x"}}, format="json")

    # The app create route has always answered 200.
    assert response.status_code == status.HTTP_200_OK, response.data
    intake_issue = IntakeIssue.objects.get(project=project)
    assert intake_issue.intake_id == intake.id
    assert intake_issue.issue.name == "x"


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_detail_routes_without_intake_row_answer_404(session_client, workspace, create_user, method):
    project = make_project(workspace, create_user, intake_view=False)
    issue = Issue.objects.create(name="Plain", project=project, workspace=workspace, created_by=create_user)
    url = f"{list_url(workspace, project)}{issue.id}/"

    kwargs = {"data": {"issue": {"name": "Renamed"}}, "format": "json"} if method == "patch" else {}
    response = getattr(session_client, method)(url, **kwargs)

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.data
    issue.refresh_from_db()
    assert issue.name == "Plain"
