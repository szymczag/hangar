# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    APIToken,
    Issue,
    IssueType,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.db.models.issue_type import ProjectIssueType


def project_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-item-types/"


def workspace_url(workspace):
    return f"/api/v1/workspaces/{workspace.slug}/work-item-types/"


def token_client(user):
    token = APIToken.objects.create(user=user, label="types", token=f"tok-{uuid4().hex}")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    return client


def add_member(workspace, project, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"types-{uid}@hangar.test", username=f"types_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    if project is not None:
        ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
    return token_client(user)


@pytest.fixture
def project(db, workspace, create_user):
    created = Project.objects.create(
        name="Types Project", identifier="TYP", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=created, member=create_user, role=20, is_active=True)
    return created


@pytest.fixture
def state(db, project, workspace):
    return State.objects.create(
        name="Todo", group="unstarted", color="#fff", project=project, workspace=workspace, default=True
    )


@pytest.mark.contract
class TestWorkItemTypeExternalAPI:
    @pytest.mark.django_db
    def test_api_key_lists_the_epic_type(self, api_key_client, workspace, project):
        assert not IssueType.objects.filter(workspace=workspace, system_key=IssueType.SystemKey.EPIC).exists()

        response = api_key_client.get(project_url(workspace, project))

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        epic = next(item for item in response.data if item["is_epic"])
        assert epic["name"] == "Epic"
        assert epic["system_key"] == "epic"
        assert epic["level"] == 1
        assert isinstance(epic["level"], int)
        assert str(project.id) in epic["project_ids"]

    @pytest.mark.django_db
    def test_missing_api_key_is_unauthorized(self, api_client, workspace, project):
        response = api_client.get(project_url(workspace, project))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.django_db
    def test_non_member_cannot_list_or_provision(self, workspace, project):
        outsider = User.objects.create(email=f"out-{uuid4().hex[:8]}@hangar.test", username=uuid4().hex)
        client = token_client(outsider)
        before = IssueType.objects.count()

        response = client.get(project_url(workspace, project))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert IssueType.objects.count() == before

    @pytest.mark.django_db
    def test_guest_can_list_and_member_cannot_create(self, workspace, project):
        guest = add_member(workspace, project, role=5)
        member = add_member(workspace, project, role=15)

        listed = guest.get(project_url(workspace, project))
        created = member.post(project_url(workspace, project), {"name": "Nope"}, format="json")

        assert listed.status_code == status.HTTP_200_OK
        assert any(item["is_epic"] for item in listed.data)
        assert created.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_create_ignores_is_epic(self, api_key_client, workspace, project):
        response = api_key_client.post(
            project_url(workspace, project),
            {"name": "Sneaky", "is_epic": True},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_epic"] is False
        assert IssueType.objects.get(pk=response.data["id"]).is_epic is False

    @pytest.mark.django_db
    def test_listed_epic_id_converts_a_work_item(self, api_key_client, workspace, project, state):
        listed = api_key_client.get(project_url(workspace, project))
        epic = next(item for item in listed.data if item["is_epic"])
        task = next(item for item in listed.data if item["system_key"] == "task")
        issue = Issue.objects.create(
            name="Future epic",
            workspace=workspace,
            project=project,
            state=state,
            type_id=task["id"],
        )

        response = api_key_client.patch(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/",
            {"type_id": epic["id"]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["is_epic"] is True
        issue.refresh_from_db()
        assert str(issue.type_id) == epic["id"]

    @pytest.mark.django_db
    def test_system_type_cannot_be_deleted(self, api_key_client, workspace, project):
        listed = api_key_client.get(project_url(workspace, project))
        epic = next(item for item in listed.data if item["is_epic"])

        response = api_key_client.delete(f"{project_url(workspace, project)}{epic['id']}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueType.objects.filter(pk=epic["id"]).exists()

    @pytest.mark.django_db
    def test_workspace_list_hides_projects_the_caller_cannot_see(self, api_key_client, workspace, project, create_user):
        api_key_client.get(project_url(workspace, project))
        hidden = Project.objects.create(
            name="Hidden", identifier="HID", workspace=workspace, created_by=create_user
        )
        epic = IssueType.objects.get(workspace=workspace, system_key=IssueType.SystemKey.EPIC)
        ProjectIssueType.objects.create(project=hidden, issue_type=epic, level=1, is_default=False)

        response = api_key_client.get(workspace_url(workspace))

        assert response.status_code == status.HTTP_200_OK
        row = next(item for item in response.data if item["is_epic"])
        assert str(project.id) in row["project_ids"]
        assert str(hidden.id) not in row["project_ids"]

    @pytest.mark.django_db
    def test_import_links_a_workspace_type_and_rejects_a_foreign_one(self, api_key_client, workspace, project, create_user):
        custom = IssueType.objects.create(workspace=workspace, name="Incident")
        other_owner = User.objects.create(email=f"own-{uuid4().hex[:8]}@hangar.test", username=uuid4().hex)
        foreign_workspace = Workspace.objects.create(
            name="Foreign", owner=other_owner, slug=f"foreign-{uuid4().hex[:6]}"
        )
        foreign = IssueType.objects.create(workspace=foreign_workspace, name="Foreign")

        imported = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/import-work-item-types/",
            {"work_item_types": [str(custom.id)]},
            format="json",
        )
        rejected = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/import-work-item-types/",
            {"work_item_types": [str(foreign.id)]},
            format="json",
        )

        assert imported.status_code == status.HTTP_204_NO_CONTENT
        assert ProjectIssueType.objects.filter(project=project, issue_type=custom).exists()
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST
        assert not ProjectIssueType.objects.filter(project=project, issue_type=foreign).exists()
