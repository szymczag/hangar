# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The roles a workshop is sold, run and delivered by.

Sales, PM and Trainers are ordinary member properties of the Workshop type, so a
coordinator can rename and reorder them. These tests hold on to the part that is
not theirs to change: the product has to be able to find the trainers.
"""

import pytest
from cryptography.fernet import Fernet
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, WorkspaceMember
from plane.ext.models import IssueProperty, IssuePropertyValue, PropertyTypeChoices, TrainerProfile
from plane.ext.services.issue_types import enable_workshops, ensure_project_system_types
from plane.ext.services.workshop_properties import (
    delivering_trainer_ids,
    set_workshop_trainers,
    sync_trainer_assignees,
    workshop_trainer_ids,
)
from plane.tests.factories import UserFactory


@pytest.fixture
def capacity(settings):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    return settings


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


def _project(workspace, owner):
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=owner)
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    State.objects.create(name="Backlog", project=project, workspace=workspace, group="backlog", default=True)
    ensure_project_system_types(project)
    return project, enable_workshops(project)


def _workshop(workspace, project, workshop_type, owner):
    return Issue.objects.create(
        name="Network security", project=project, workspace=workspace, type=workshop_type, created_by=owner
    )


def _trainer(workspace, project):
    user = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=15)
    TrainerProfile.objects.create(workspace=workspace, user=user, status=TrainerProfile.Status.ACTIVE)
    return user


def _property(workshop_type, system_key):
    return IssueProperty.objects.get(issue_type=workshop_type, system_key=system_key, deleted_at__isnull=True)


@pytest.mark.contract
@pytest.mark.django_db
def test_enabling_workshops_provisions_the_three_roles(capacity, workspace, create_user):
    _, workshop_type = _project(workspace, create_user)

    roles = {
        prop.system_key: prop
        for prop in IssueProperty.objects.filter(issue_type=workshop_type, deleted_at__isnull=True)
    }

    assert set(roles) == {
        IssueProperty.SystemKey.SALES,
        IssueProperty.SystemKey.PROJECT_MANAGER,
        IssueProperty.SystemKey.TRAINER,
    }
    assert all(prop.property_type == PropertyTypeChoices.MEMBER for prop in roles.values())
    assert roles[IssueProperty.SystemKey.TRAINER].is_multi
    assert not roles[IssueProperty.SystemKey.SALES].is_multi


@pytest.mark.contract
@pytest.mark.django_db
def test_a_renamed_role_is_still_found_by_the_product(capacity, workspace, create_user):
    """Display names belong to the coordinator; the system key is what the code reads."""
    project, workshop_type = _project(workspace, create_user)
    trainers = _property(workshop_type, IssueProperty.SystemKey.TRAINER)
    trainer = _trainer(workspace, project)
    issue = _workshop(workspace, project, workshop_type, create_user)
    client, csrf = _client(create_user)

    renamed = client.patch(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/properties/{trainers.id}/",
        {"display_name": "Prowadzący"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    set_workshop_trainers(issue, [trainer.id])

    assert renamed.status_code == status.HTTP_200_OK
    assert workshop_trainer_ids(issue) == [trainer.id]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_role_property_cannot_be_deleted(capacity, workspace, create_user):
    """Losing it would take the trainers away from the planner and the checklists."""
    project, workshop_type = _project(workspace, create_user)
    trainers = _property(workshop_type, IssueProperty.SystemKey.TRAINER)
    client, csrf = _client(create_user)

    response = client.delete(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/properties/{trainers.id}/",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "system_property"
    assert IssueProperty.objects.filter(pk=trainers.pk, deleted_at__isnull=True).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_naming_a_trainer_assigns_them_to_the_workshop(capacity, workspace, create_user):
    """The ledger and the planner ask the work item's assignees who is delivering it."""
    project, workshop_type = _project(workspace, create_user)
    trainers = _property(workshop_type, IssueProperty.SystemKey.TRAINER)
    trainer = _trainer(workspace, project)
    issue = _workshop(workspace, project, workshop_type, create_user)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/property-values/",
        {str(trainers.id): [str(trainer.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert issue.issue_assignee.filter(assignee_id=trainer.id).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_somebody_who_cannot_hold_work_here_is_reported_rather_than_assigned(capacity, workspace, create_user):
    project, workshop_type = _project(workspace, create_user)
    outsider = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
    issue = _workshop(workspace, project, workshop_type, create_user)
    set_workshop_trainers(issue, [outsider.id])

    result = sync_trainer_assignees(issue)

    assert result == {"assigned": [], "skipped": [str(outsider.id)]}
    assert not issue.issue_assignee.exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_dropping_a_trainer_from_the_property_leaves_the_assignment_alone(capacity, workspace, create_user):
    """They may still hold subtasks; unassigning them is a decision for a person."""
    project, workshop_type = _project(workspace, create_user)
    trainer = _trainer(workspace, project)
    issue = _workshop(workspace, project, workshop_type, create_user)
    set_workshop_trainers(issue, [trainer.id])
    sync_trainer_assignees(issue)

    set_workshop_trainers(issue, [])
    sync_trainer_assignees(issue)

    assert workshop_trainer_ids(issue) == []
    assert issue.issue_assignee.filter(assignee_id=trainer.id).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_workshop_from_before_the_property_falls_back_to_its_assignees(capacity, workspace, create_user):
    """Every workshop that already exists has assignees and no property values."""
    project, workshop_type = _project(workspace, create_user)
    trainer = _trainer(workspace, project)
    issue = _workshop(workspace, project, workshop_type, create_user)
    issue.issue_assignee.create(assignee_id=trainer.id, project=project, workspace=workspace)

    assert workshop_trainer_ids(issue) == []
    assert delivering_trainer_ids(issue) == [trainer.id]


@pytest.mark.contract
@pytest.mark.django_db
def test_the_property_keeps_the_order_it_was_given(capacity, workspace, create_user):
    """Sessions start from this list, so "the first trainer" has to mean something."""
    project, workshop_type = _project(workspace, create_user)
    first = _trainer(workspace, project)
    second = _trainer(workspace, project)
    issue = _workshop(workspace, project, workshop_type, create_user)

    set_workshop_trainers(issue, [second.id, first.id])

    assert workshop_trainer_ids(issue) == [second.id, first.id]
    assert IssuePropertyValue.objects.filter(issue=issue).count() == 2
