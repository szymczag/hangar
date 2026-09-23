# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The Workshop type is offered only by projects that chose to offer it.

It used to arrive in every project as soon as anybody in the workspace became a
trainer. These tests hold the opposite rule in place, including against the
routes that used to switch it on as a side effect.
"""

import pytest
from cryptography.fernet import Fernet
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueType, Project, ProjectMember, State, WorkspaceMember
from plane.db.models.issue_type import ProjectIssueType
from plane.ext.models import TrainerProfile
from plane.ext.services.issue_types import (
    enable_workshops,
    ensure_project_system_types,
    workshops_enabled,
)


@pytest.fixture
def capacity(settings):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    return settings


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


def _project(workspace, owner, *, role=20, identifier="TRN"):
    project = Project.objects.create(
        name=f"Training {identifier}", identifier=identifier, workspace=workspace, created_by=owner
    )
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=role)
    State.objects.create(name="Backlog", project=project, workspace=workspace, group="backlog", default=True)
    ensure_project_system_types(project)
    return project


def _url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/capacity/workshops/"


@pytest.mark.contract
@pytest.mark.django_db
def test_becoming_a_trainer_no_longer_puts_workshops_in_every_project(capacity, workspace, create_user):
    """The side effect this change removes."""
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)

    ensure_project_system_types(project)

    assert not workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_administrator_turns_workshops_on(capacity, workspace, create_user):
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    response = client.put(_url(workspace, project), {"enabled": True}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"enabled": True, "workshop_count": 0}
    assert workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_member_cannot_turn_workshops_on(capacity, workspace, create_user):
    # Demoted in the workspace as well: a workspace administrator who belongs to
    # the project may change it whatever their project role, which is the
    # platform's own rule and is tested separately below.
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=15)
    project = _project(workspace, create_user, role=15)
    client, csrf = _client(create_user)

    response = client.put(_url(workspace, project), {"enabled": True}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_workspace_administrator_may_turn_workshops_on_in_a_project_they_belong_to(capacity, workspace, create_user):
    """The platform's rule for every project setting, and deliberately not an exception here.

    Making Workshops the one project setting a workspace administrator could not
    change would be a surprise with no reason behind it.
    """
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=20)
    project = _project(workspace, create_user, role=15)
    client, csrf = _client(create_user)

    response = client.put(_url(workspace, project), {"enabled": True}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_200_OK
    assert workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_turning_workshops_off_is_refused_while_the_project_holds_one(capacity, workspace, create_user):
    """They would be left as work items of a type their project no longer offers."""
    project = _project(workspace, create_user)
    workshop = enable_workshops(project)
    Issue.objects.create(name="A workshop", project=project, workspace=workspace, type=workshop, created_by=create_user)
    client, csrf = _client(create_user)

    response = client.put(_url(workspace, project), {"enabled": False}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "workshops_in_use"
    assert workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_turning_workshops_off_and_on_again_works(capacity, workspace, create_user):
    """The link is soft-deleted, and the uniqueness condition must still allow a new one."""
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    client.put(_url(workspace, project), {"enabled": True}, format="json", HTTP_X_CSRFTOKEN=csrf)
    client.put(_url(workspace, project), {"enabled": False}, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert not workshops_enabled(project)

    response = client.put(_url(workspace, project), {"enabled": True}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_200_OK
    assert workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_without_workshops_refuses_a_new_one(capacity, workspace, create_user):
    """Hidden in the picker is not enough; the server has to refuse it too.

    Work item creation already validates the type against the project's links,
    which is why the opt-in is the link itself rather than a separate flag the
    creation path would also have to learn about.
    """
    other = _project(workspace, create_user, identifier="ONE")
    enable_workshops(other)
    project = _project(workspace, create_user, identifier="TWO")
    workshop = IssueType.objects.get(workspace=workspace, system_key=IssueType.SystemKey.WORKSHOP)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/",
        {"name": "Not allowed here", "type_id": str(workshop.id)},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Issue.objects.filter(project=project, type=workshop).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_importing_into_a_project_without_workshops_is_refused(capacity, workspace, create_user):
    """Importing used to switch the type on as a side effect -- the back door."""
    project = _project(workspace, create_user)
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=20)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": ["00000000-0000-0000-0000-000000000000"]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "workshops_not_enabled"
    assert not workshops_enabled(project)


@pytest.mark.contract
@pytest.mark.django_db
def test_the_migration_keeps_workshops_where_they_are_used(capacity, workspace, create_user):
    """The decision this release makes about projects that were given the type unasked."""
    import importlib

    from django.apps import apps as django_apps

    migration = importlib.import_module("plane.ext.migrations.0037_workshops_per_project")

    used = _project(workspace, create_user, identifier="USE")
    unused = _project(workspace, create_user, identifier="NOT")
    workshop = enable_workshops(used)
    enable_workshops(unused)
    Issue.objects.create(name="Kept", project=used, workspace=workspace, type=workshop, created_by=create_user)

    migration.retire_unused_workshop_links(django_apps, None)

    assert workshops_enabled(used)
    assert not workshops_enabled(unused)
    assert ProjectIssueType.all_objects.filter(project=unused, issue_type=workshop).exists()
