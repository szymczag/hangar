# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
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


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Epic Project",
        identifier="EPC",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def default_state(db, project, workspace):
    return State.objects.create(
        name="Todo", group="unstarted", color="#ff0000", project=project, workspace=workspace, default=True
    )


@pytest.fixture
def completed_state(db, project, workspace):
    return State.objects.create(
        name="Done", group="completed", color="#00ff00", project=project, workspace=workspace
    )


def make_role_client(workspace, project, role):
    """A client authenticated as a fresh user with the given project role."""
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"user-{uid}@hangar.test", username=f"user_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def enable_epics(client, workspace, project):
    return client.patch(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-settings/",
        {"is_epic_enabled": True},
        format="json",
    )


def create_epic(client, workspace, project, name="Big rock", **extra):
    return client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/",
        {"name": name, **extra},
        format="json",
    )


@pytest.mark.contract
class TestEpicSettings:
    @pytest.mark.django_db
    def test_admin_enables_epics(self, session_client, workspace, project, default_state):
        response = enable_epics(session_client, workspace, project)
        assert response.status_code == status.HTTP_200_OK
        assert ProjectIssueType.objects.filter(project=project, issue_type__is_epic=True).exists()

        get_response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-settings/")
        assert get_response.data["is_epic_enabled"] is True

    @pytest.mark.django_db
    def test_member_cannot_toggle_epics(self, workspace, project, default_state):
        client, _ = make_role_client(workspace, project, role=15)
        response = enable_epics(client, workspace, project)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_disable_keeps_epics(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        create_epic(session_client, workspace, project, state_id=str(default_state.id))
        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-settings/",
            {"is_epic_enabled": False},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert not ProjectIssueType.objects.filter(project=project, issue_type__is_epic=True).exists()
        # Data retained
        assert Issue.objects.filter(project=project, type__is_epic=True).exists()


@pytest.mark.contract
class TestEpicCRUD:
    @pytest.mark.django_db
    def test_create_epic(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        response = create_epic(session_client, workspace, project, state_id=str(default_state.id))
        assert response.status_code == status.HTTP_201_CREATED
        epic = Issue.objects.get(pk=response.data["id"])
        assert epic.type.is_epic is True

    @pytest.mark.django_db
    def test_create_requires_enablement(self, session_client, workspace, project, default_state):
        response = create_epic(session_client, workspace, project, state_id=str(default_state.id))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_guest_cannot_create_epic(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        guest_client, _ = make_role_client(workspace, project, role=5)
        response = create_epic(guest_client, workspace, project, state_id=str(default_state.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_client_supplied_type_is_ignored(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        rogue_type = IssueType.objects.create(workspace=workspace, name="Rogue", is_epic=False)
        response = create_epic(
            session_client, workspace, project, state_id=str(default_state.id), type=str(rogue_type.id)
        )
        assert response.status_code == status.HTTP_201_CREATED
        epic = Issue.objects.get(pk=response.data["id"])
        assert epic.type.is_epic is True
        assert epic.type_id != rogue_type.id

    @pytest.mark.django_db
    def test_update_cannot_change_type(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        rogue_type = IssueType.objects.create(workspace=workspace, name="Rogue", is_epic=False)
        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/",
            {"name": "Renamed rock", "type": str(rogue_type.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        epic = Issue.objects.get(pk=epic_id)
        assert epic.name == "Renamed rock"
        assert epic.type.is_epic is True

    @pytest.mark.django_db
    def test_epics_and_issues_are_separated(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        issue = Issue.objects.create(
            name="Normal work item", project=project, workspace=workspace, state=default_state
        )

        # Epic list contains only the epic
        response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/")
        assert response.status_code == status.HTTP_200_OK
        ids = {item["id"] for item in response.data}
        assert str(epic_id) in {str(i) for i in ids}
        assert str(issue.id) not in {str(i) for i in ids}

        # Work-item manager excludes epics (drives every issue list surface)
        work_item_ids = set(
            Issue.issue_objects.filter(project=project).values_list("id", flat=True)
        )
        assert issue.id in work_item_ids
        assert str(epic_id) not in {str(i) for i in work_item_ids}


@pytest.mark.contract
class TestEpicScoping:
    @pytest.mark.django_db
    def test_cross_tenant_epic_access_denied(self, session_client, workspace, project, default_state):
        # Victim tenant with its own epic
        uid = uuid4().hex[:8]
        victim = User.objects.create(email=f"victim-{uid}@hangar.test", username=f"victim_{uid}")
        victim_ws = Workspace.objects.create(name="Victim WS", slug=f"victim-{uid}", owner=victim)
        WorkspaceMember.objects.create(workspace=victim_ws, member=victim, role=20, is_active=True)
        victim_project = Project.objects.create(
            name="Victim P", identifier="VIC", workspace=victim_ws, created_by=victim
        )
        ProjectMember.objects.create(project=victim_project, member=victim, role=20, is_active=True)
        victim_state = State.objects.create(
            name="Todo", group="unstarted", color="#fff", project=victim_project, workspace=victim_ws
        )
        victim_type = IssueType.objects.create(workspace=victim_ws, name="Epic", is_epic=True)
        ProjectIssueType.objects.create(project=victim_project, issue_type=victim_type)
        victim_epic = Issue.objects.create(
            name="Victim epic",
            project=victim_project,
            workspace=victim_ws,
            state=victim_state,
            type=victim_type,
        )

        # Attacker (admin of their own project) probes the victim's epic
        response = session_client.get(
            f"/api/workspaces/{victim_ws.slug}/projects/{victim_project.id}/epics/{victim_epic.id}/"
        )
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    @pytest.mark.django_db
    def test_children_progress(self, session_client, workspace, project, default_state, completed_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        Issue.objects.create(
            name="Child 1", project=project, workspace=workspace, state=default_state, parent_id=epic_id
        )
        Issue.objects.create(
            name="Child 2", project=project, workspace=workspace, state=completed_state, parent_id=epic_id
        )

        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/issues/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["progress"]["total_issues"] == 2
        assert response.data["progress"]["completed_issues"] == 1
        assert len(response.data["issues"]) == 2
