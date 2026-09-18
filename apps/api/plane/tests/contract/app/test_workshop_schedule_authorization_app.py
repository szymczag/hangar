# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, WorkspaceMember
from plane.ext.models import TrainerProfile, WorkshopSchedule, WorkshopSession
from plane.ext.services.issue_types import ensure_project_workshop_type
from plane.tests.factories import UserFactory

STARTS = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def capacity(settings):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    return settings


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


def _project(workspace, owner):
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=owner)
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    State.objects.create(name="Backlog", project=project, workspace=workspace, group="backlog", default=True)
    return project


def _workshop(project, owner, trainer_user, *, name="NetSec workshop"):
    issue = Issue.objects.create(
        name=name,
        project=project,
        workspace=project.workspace,
        type=ensure_project_workshop_type(project),
        created_by=owner,
    )
    issue.issue_assignee.create(assignee=trainer_user, project=project, workspace=project.workspace)
    return issue


def _session(issue, trainer_user, *, starts=STARTS, hours=4):
    schedule = WorkshopSchedule.objects.create(issue=issue, starts_at=starts, ends_at=starts + timedelta(hours=hours))
    session = WorkshopSession.objects.create(
        schedule=schedule, position=0, starts_at=starts, ends_at=starts + timedelta(hours=hours)
    )
    session.trainers.add(trainer_user)
    return session


def _payload(sessions):
    return {"sessions": sessions}


def _one(starts=STARTS, hours=4, trainer_ids=None):
    body = {
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(hours=hours)).isoformat(),
    }
    if trainer_ids:
        body["trainer_ids"] = trainer_ids
    return body


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_guest_cannot_schedule_a_workshop(capacity, workspace, create_user):
    """Two routes reach the same mutation and used to disagree about who may.

    The work-item route is project ADMIN/MEMBER, which excludes a guest. The
    planner route checked workspace role and then only project *membership*, so
    a guest passed and could assign a trainer and write sessions.
    """
    project = _project(workspace, create_user)
    guest = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=15)
    ProjectMember.objects.create(project=project, member=guest, workspace=workspace, role=5)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, create_user)
    client, csrf = _client(guest)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        _payload([_one()]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
    assert WorkshopSession.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_member_can_still_schedule(capacity, workspace, create_user):
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, create_user)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        _payload([_one()]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_200_OK
    assert WorkshopSession.objects.count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_a_session_may_not_be_placed_on_top_of_another_workshop(capacity, workspace, create_user):
    """The gap that let the editor write a booking the planner would refuse."""
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    taken = _workshop(project, create_user, create_user, name="Already booked")
    _session(taken, create_user)
    issue = _workshop(project, create_user, create_user)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        _payload([_one(starts=STARTS + timedelta(hours=1))]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "collides" in response.data["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_workshop_can_still_be_edited_without_colliding_with_itself(capacity, workspace, create_user):
    """Its own sessions are about to be replaced, so they must not block."""
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, create_user)
    _session(issue, create_user)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        _payload([_one(starts=STARTS + timedelta(minutes=30))]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.contract
@pytest.mark.django_db
def test_two_submitted_sessions_may_not_put_one_trainer_in_two_places(capacity, workspace, create_user):
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, create_user)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        _payload([_one(), _one(starts=STARTS + timedelta(hours=2))]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "two places at once" in response.data["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_consecutive_sessions_are_allowed(capacity, workspace, create_user):
    """A two-day workshop is the ordinary case and must keep working."""
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, create_user)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        _payload([_one(), _one(starts=STARTS + timedelta(days=1))]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_200_OK
    assert WorkshopSession.objects.count() == 2
