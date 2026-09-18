# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueAssignee, Project, ProjectMember, State, WorkspaceMember
from plane.ext.models import (
    TrainerProfile,
    WorkshopChecklistOrigin,
    WorkshopChecklistTemplate,
    WorkshopSchedule,
    WorkshopSession,
)
from plane.ext.services.issue_types import ensure_project_system_types, ensure_project_workshop_type
from plane.tests.factories import UserFactory


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


def _project(workspace, owner):
    project = Project.objects.create(
        name="Training", identifier="TRN", workspace=workspace, created_by=owner
    )
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    State.objects.create(name="Backlog", project=project, workspace=workspace, group="backlog", default=True)
    ensure_project_system_types(project)
    ensure_project_workshop_type(project)
    return project


def _workshop(project, owner, *, assignees=()):
    issue = Issue.objects.create(
        name="NetSec workshop",
        project=project,
        workspace=project.workspace,
        type=ensure_project_workshop_type(project),
        created_by=owner,
    )
    for assignee in assignees:
        IssueAssignee.objects.create(
            issue=issue, assignee=assignee, project=project, workspace=project.workspace
        )
    return issue


def _template_payload(**overrides):
    payload = {
        "name": "Standard workshop",
        "is_default": True,
        "items": [
            {"title": "Prepare materials", "assignee_mode": "workshop_trainer", "offset_days": -7},
            {"title": "Publish stream link", "assignee_mode": "unassigned", "offset_days": -1},
            {"title": "Collect feedback", "assignee_mode": "unassigned", "offset_days": 1},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.contract
@pytest.mark.django_db
def test_the_endpoints_are_invisible_while_the_feature_is_off(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = False
    client, _ = _client(create_user)

    response = client.get(f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
@pytest.mark.django_db
def test_an_administrator_defines_a_template_and_everyone_can_read_it(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/"

    created = client.post(url, _template_payload(), format="json", HTTP_X_CSRFTOKEN=csrf)

    assert created.status_code == status.HTTP_201_CREATED
    assert [item["position"] for item in created.data["items"]] == [0, 1, 2]
    assert client.get(url).data["results"][0]["name"] == "Standard workshop"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_cannot_define_a_template(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    member = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    client, csrf = _client(member)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_two_items_may_not_share_a_title(settings, workspace, create_user):
    """The checklist is applied by name, so a duplicate would be unappliable."""
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(items=[{"title": "Prepare"}, {"title": "prepare"}]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
def test_editing_a_template_replaces_its_items_without_colliding_with_the_old_positions(
    settings, workspace, create_user
):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/"
    template_id = client.post(url, _template_payload(), format="json", HTTP_X_CSRFTOKEN=csrf).data["id"]

    response = client.put(
        f"{url}{template_id}/",
        _template_payload(items=[{"title": "Collect feedback", "offset_days": 2}]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_200_OK
    assert [item["title"] for item in response.data["items"]] == ["Collect feedback"]


@pytest.mark.contract
@pytest.mark.django_db
def test_only_a_workshop_takes_a_checklist(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    task_type, _ = ensure_project_system_types(project)
    task = Issue.objects.create(
        name="Ordinary task", project=project, workspace=workspace, type=task_type, created_by=create_user
    )
    template = WorkshopChecklistTemplate.objects.create(workspace=workspace, name="Standard")
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{task.id}/apply-checklist/",
        {"template_id": str(template.id)},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
def test_applying_a_template_creates_the_subtasks_and_assigns_the_workshop_s_trainer(
    settings, workspace, create_user
):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, assignees=[create_user])
    client, csrf = _client(create_user)
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_201_CREATED
    children = Issue.objects.filter(parent=issue).order_by("created_at")
    assert [child.name for child in children] == [
        "Prepare materials",
        "Publish stream link",
        "Collect feedback",
    ]
    materials = children.get(name="Prepare materials")
    assert list(materials.issue_assignee.values_list("assignee_id", flat=True)) == [create_user.id]
    # Every child carries its offset, because the workshop has no date yet and
    # these will have to be dated later.
    assert WorkshopChecklistOrigin.objects.filter(issue__in=children).count() == 3
    assert all(child.target_date is None for child in children)


@pytest.mark.contract
@pytest.mark.django_db
def test_applying_the_same_template_twice_does_not_double_the_checklist(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    issue = _workshop(project, create_user)
    client, csrf = _client(create_user)
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/"

    client.post(url, {"template_id": template_id}, format="json", HTTP_X_CSRFTOKEN=csrf)
    second = client.post(url, {"template_id": template_id}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert second.data["created"] == []
    assert Issue.objects.filter(parent=issue).count() == 3


@pytest.mark.contract
@pytest.mark.django_db
def test_an_assignee_who_cannot_hold_work_here_is_reported_rather_than_silently_dropped(
    settings, workspace, create_user
):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    issue = _workshop(project, create_user)
    outsider = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
    client, csrf = _client(create_user)
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(
            items=[{"title": "Publish stream link", "assignee_mode": "fixed", "assignee_id": str(outsider.id)}]
        ),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.data["skipped_assignees"] == [str(outsider.id)]
    child = Issue.objects.get(parent=issue)
    assert child.issue_assignee.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_a_role_assigns_everyone_who_currently_holds_it(settings, workspace, create_user):
    """The point of a role: the template names the job, not the people."""
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    issue = _workshop(project, create_user)
    second = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=second, role=15)
    ProjectMember.objects.create(project=project, member=second, workspace=workspace, role=15)
    client, csrf = _client(create_user)
    roles_url = f"/api/workspaces/{workspace.slug}/capacity/workshop-roles/"

    role_id = client.post(
        roles_url,
        {"name": "Streaming", "member_ids": [str(create_user.id), str(second.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(
            items=[{"title": "Publish stream link", "assignee_mode": "role", "role_id": role_id, "offset_days": -1}]
        ),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_201_CREATED
    child = Issue.objects.get(parent=issue, name="Publish stream link")
    assert set(child.issue_assignee.values_list("assignee_id", flat=True)) == {create_user.id, second.id}


@pytest.mark.contract
@pytest.mark.django_db
def test_changing_who_holds_a_role_changes_the_next_workshop_without_touching_the_template(
    settings, workspace, create_user
):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    successor = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=successor, role=15)
    ProjectMember.objects.create(project=project, member=successor, workspace=workspace, role=15)
    client, csrf = _client(create_user)
    roles_url = f"/api/workspaces/{workspace.slug}/capacity/workshop-roles/"
    role_id = client.post(
        roles_url, {"name": "Streaming", "member_ids": [str(create_user.id)]}, format="json", HTTP_X_CSRFTOKEN=csrf
    ).data["id"]
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(items=[{"title": "Publish stream link", "assignee_mode": "role", "role_id": role_id}]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]

    # The rota changes. The template is not touched.
    client.put(
        f"{roles_url}{role_id}/",
        {"name": "Streaming", "member_ids": [str(successor.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    issue = _workshop(project, create_user)
    client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    child = Issue.objects.get(parent=issue, name="Publish stream link")
    assert list(child.issue_assignee.values_list("assignee_id", flat=True)) == [successor.id]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_role_nobody_holds_leaves_the_subtask_unassigned_rather_than_failing(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    issue = _workshop(project, create_user)
    client, csrf = _client(create_user)
    role_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/workshop-roles/",
        {"name": "Feedback", "member_ids": []},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(items=[{"title": "Collect feedback", "assignee_mode": "role", "role_id": role_id}]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Issue.objects.get(parent=issue, name="Collect feedback").issue_assignee.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_a_checklist_item_in_role_mode_requires_a_role_that_exists_here(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(items=[{"title": "Publish stream link", "assignee_mode": "role"}]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
def test_deleting_a_role_leaves_the_template_standing(settings, workspace, create_user):
    """A deleted role must not take checklist items down with it."""
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client, csrf = _client(create_user)
    roles_url = f"/api/workspaces/{workspace.slug}/capacity/workshop-roles/"
    role_id = client.post(
        roles_url, {"name": "Streaming", "member_ids": []}, format="json", HTTP_X_CSRFTOKEN=csrf
    ).data["id"]
    templates_url = f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/"
    template_id = client.post(
        templates_url,
        _template_payload(items=[{"title": "Publish stream link", "assignee_mode": "role", "role_id": role_id}]),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]

    assert client.delete(f"{roles_url}{role_id}/", HTTP_X_CSRFTOKEN=csrf).status_code == status.HTTP_204_NO_CONTENT

    template = next(row for row in client.get(templates_url).data["results"] if row["id"] == template_id)
    assert [item["title"] for item in template["items"]] == ["Publish stream link"]
    assert template["items"][0]["role_id"] is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_cannot_change_the_rota(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    member = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    client, csrf = _client(member)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/workshop-roles/",
        {"name": "Streaming", "member_ids": []},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_scheduling_the_workshop_dates_a_checklist_that_had_no_date_yet(settings, workspace, create_user):
    """The whole reason the offset is stored rather than resolved on creation.

    A Workshop exists before it has a date, so its checklist cannot be dated
    when it is created. Scheduling is the moment that becomes possible.
    """
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, assignees=[create_user])
    client, csrf = _client(create_user)
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]
    client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    starts_at = (timezone.now() + timedelta(days=30)).replace(hour=9, minute=0, second=0, microsecond=0)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        {
            "sessions": [
                {
                    "starts_at": starts_at.isoformat(),
                    "ends_at": (starts_at + timedelta(hours=4)).isoformat(),
                    "trainer_ids": [str(create_user.id)],
                }
            ]
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_200_OK
    materials = Issue.objects.get(parent=issue, name="Prepare materials")
    feedback = Issue.objects.get(parent=issue, name="Collect feedback")
    assert materials.target_date == (starts_at - timedelta(days=7)).date()
    assert feedback.target_date == (starts_at + timedelta(days=1)).date()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_date_somebody_set_by_hand_survives_scheduling(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    project = _project(workspace, create_user)
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    issue = _workshop(project, create_user, assignees=[create_user])
    client, csrf = _client(create_user)
    template_id = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/checklist-templates/",
        _template_payload(),
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).data["id"]
    client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/apply-checklist/",
        {"template_id": template_id},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    chosen = (timezone.now() + timedelta(days=3)).date()
    Issue.objects.filter(parent=issue, name="Collect feedback").update(target_date=chosen)
    starts_at = (timezone.now() + timedelta(days=30)).replace(hour=9, minute=0, second=0, microsecond=0)

    client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        {
            "sessions": [
                {
                    "starts_at": starts_at.isoformat(),
                    "ends_at": (starts_at + timedelta(hours=4)).isoformat(),
                    "trainer_ids": [str(create_user.id)],
                }
            ]
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert Issue.objects.get(parent=issue, name="Collect feedback").target_date == chosen
