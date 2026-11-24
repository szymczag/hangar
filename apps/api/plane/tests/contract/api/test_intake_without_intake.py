# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The external intake create route refuses a project whose intake has no row or is
turned off, and writes nothing."""

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
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/intake-issues/"


@pytest.mark.contract
@pytest.mark.django_db
def test_create_with_intake_view_on_but_no_row_is_refused(api_key_client, workspace, create_user):
    project = make_project(workspace, create_user, intake_view=True)
    issues_before = Issue.all_objects.filter(project=project).count()

    response = api_key_client.post(list_url(workspace, project), {"issue": {"name": "x"}}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
    assert Issue.all_objects.filter(project=project).count() == issues_before


@pytest.mark.contract
@pytest.mark.django_db
def test_create_with_row_but_intake_turned_off_is_refused(api_key_client, workspace, create_user):
    project = make_project(workspace, create_user, intake_view=False)
    Intake.objects.create(name="Intake", project=project, workspace=workspace, is_default=True)
    issues_before = Issue.all_objects.filter(project=project).count()

    response = api_key_client.post(list_url(workspace, project), {"issue": {"name": "x"}}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
    assert Issue.all_objects.filter(project=project).count() == issues_before
    assert not IntakeIssue.all_objects.filter(project=project).exists()
