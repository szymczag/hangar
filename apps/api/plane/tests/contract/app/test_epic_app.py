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
    ProjectUserProperty,
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
    return State.objects.create(name="Done", group="completed", color="#00ff00", project=project, workspace=workspace)


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
    def test_system_epic_type_cannot_be_disabled(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        create_epic(session_client, workspace, project, state_id=str(default_state.id))
        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-settings/",
            {"is_epic_enabled": False},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ProjectIssueType.objects.filter(project=project, issue_type__is_epic=True).exists()
        assert Issue.objects.filter(project=project, type__is_epic=True).exists()

    @pytest.mark.django_db
    def test_string_false_is_rejected(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-settings/",
            {"is_epic_enabled": "false"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
class TestEpicCRUD:
    @pytest.mark.django_db
    def test_create_epic(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        response = create_epic(session_client, workspace, project, state_id=str(default_state.id))
        assert response.status_code == status.HTTP_201_CREATED, response.data
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
        assert response.status_code == status.HTTP_201_CREATED, response.data
        epic = Issue.objects.get(pk=response.data["id"])
        assert epic.type.is_epic is True
        assert epic.type_id != rogue_type.id

    @pytest.mark.django_db
    def test_create_forces_visible_top_level_epic(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        parent = Issue.objects.create(
            name="Ordinary parent",
            project=project,
            workspace=workspace,
            state=default_state,
        )
        response = create_epic(
            session_client,
            workspace,
            project,
            state_id=str(default_state.id),
            parent_id=str(parent.id),
            is_draft=True,
            archived_at="2026-01-01",
            deleted_at="2026-01-01T00:00:00Z",
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        epic = Issue.objects.get(pk=response.data["id"])
        assert epic.parent_id is None
        assert epic.is_draft is False
        assert epic.archived_at is None
        assert epic.deleted_at is None

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
    def test_update_cannot_hide_or_parent_epic(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        parent = Issue.objects.create(
            name="Ordinary parent",
            project=project,
            workspace=workspace,
            state=default_state,
        )
        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/",
            {
                "parent_id": str(parent.id),
                "is_draft": True,
                "archived_at": "2026-01-01",
                "deleted_at": "2026-01-01T00:00:00Z",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        epic = Issue.objects.get(pk=epic_id)
        assert epic.parent_id is None
        assert epic.is_draft is False
        assert epic.archived_at is None
        assert epic.deleted_at is None

    @pytest.mark.django_db
    def test_epics_are_in_the_work_item_manager(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        issue = Issue.objects.create(name="Normal work item", project=project, workspace=workspace, state=default_state)

        # Epic list contains only the epic
        response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_count"] == 1
        ids = {item["id"] for item in response.data["results"]}
        assert str(epic_id) in {str(i) for i in ids}
        assert str(issue.id) not in {str(i) for i in ids}

        # Epic is an ordinary work-item type and shares the same manager.
        work_item_ids = set(Issue.issue_objects.filter(project=project).values_list("id", flat=True))
        assert issue.id in work_item_ids
        assert str(epic_id) in {str(i) for i in work_item_ids}

    @pytest.mark.django_db
    def test_epic_uses_default_state_when_not_supplied(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)

        response = create_epic(session_client, workspace, project)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert Issue.objects.get(pk=response.data["id"]).state_id == default_state.id


@pytest.mark.contract
class TestUnifiedEpicWorkItems:
    @pytest.mark.django_db
    def test_create_list_and_retrieve_epic_through_work_items(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_type = IssueType.objects.get(workspace=workspace, system_key=IssueType.SystemKey.EPIC)

        created = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/",
            {"name": "Unified epic", "state_id": str(default_state.id), "type_id": str(epic_type.id)},
            format="json",
        )

        assert created.status_code == status.HTTP_201_CREATED, created.data
        assert created.data["type_id"] == epic_type.id
        assert created.data["is_epic"] is True

        listing = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/")
        assert listing.status_code == status.HTTP_200_OK
        listed = next(item for item in listing.data["results"] if str(item["id"]) == str(created.data["id"]))
        assert listed["type_id"] == epic_type.id
        assert listed["is_epic"] is True

        detail = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{created.data['id']}/"
        )
        assert detail.status_code == status.HTTP_200_OK
        assert detail.data["type_id"] == epic_type.id
        assert detail.data["is_epic"] is True

    @pytest.mark.django_db
    def test_work_item_endpoint_rejects_unlinked_type(self, session_client, workspace, project, default_state):
        rogue_type = IssueType.objects.create(workspace=workspace, name="Rogue")

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/",
            {"name": "Invalid", "state_id": str(default_state.id), "type_id": str(rogue_type.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type_id" in response.data

    @pytest.mark.django_db
    def test_work_item_endpoint_rejects_null_type(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/",
            {"name": "Untyped", "state_id": str(default_state.id), "type_id": None},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type_id" in response.data

    @pytest.mark.django_db
    def test_work_item_endpoint_rejects_epic_parent(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project).data["id"]
        parent = Issue.objects.create(name="Parent", project=project, workspace=workspace, state=default_state)

        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{epic_id}/",
            {"parent_id": str(parent.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "parent_id" in response.data

    @pytest.mark.django_db
    def test_full_update_uses_the_same_epic_hierarchy_validation(
        self, session_client, workspace, project, default_state
    ):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project).data["id"]
        epic_type = IssueType.objects.get(workspace=workspace, system_key=IssueType.SystemKey.EPIC)
        parent = Issue.objects.create(name="Parent", project=project, workspace=workspace, state=default_state)

        response = session_client.put(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{epic_id}/",
            {
                "name": "Epic",
                "state_id": str(default_state.id),
                "type_id": str(epic_type.id),
                "parent_id": str(parent.id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "parent_id" in response.data

    @pytest.mark.django_db
    def test_guest_cannot_full_update_work_item(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project).data["id"]
        guest_client, _ = make_role_client(workspace, project, role=5)

        response = guest_client.put(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{epic_id}/",
            {"name": "Changed by guest", "state_id": str(default_state.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_standard_sub_issues_endpoint_attaches_child(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project).data["id"]
        child = Issue.objects.create(name="Child", project=project, workspace=workspace, state=default_state)

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{epic_id}/sub-issues/",
            {"sub_issue_ids": [str(child.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        child.refresh_from_db()
        assert str(child.parent_id) == str(epic_id)
        assert {str(item["id"]) for item in response.data["sub_issues"]} == {str(child.id)}

    @pytest.mark.django_db
    def test_standard_sub_issues_endpoint_rejects_epic_as_child(
        self, session_client, workspace, project, default_state
    ):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, name="Child epic").data["id"]
        parent = Issue.objects.create(name="Parent", project=project, workspace=workspace, state=default_state)

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{parent.id}/sub-issues/",
            {"sub_issue_ids": [str(epic_id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Issue.objects.get(pk=epic_id).parent_id is None

    @pytest.mark.django_db
    def test_standard_sub_issues_endpoint_rejects_cycle(self, session_client, workspace, project, default_state):
        parent = Issue.objects.create(name="Parent", project=project, workspace=workspace, state=default_state)
        child = Issue.objects.create(
            name="Child", project=project, workspace=workspace, state=default_state, parent=parent
        )

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{child.id}/sub-issues/",
            {"sub_issue_ids": [str(parent.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        parent.refresh_from_db()
        assert parent.parent_id is None

    @pytest.mark.django_db
    def test_standard_sub_issues_endpoint_bounds_bulk_assignment(
        self, session_client, workspace, project, default_state
    ):
        parent = Issue.objects.create(name="Parent", project=project, workspace=workspace, state=default_state)

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{parent.id}/sub-issues/",
            {"sub_issue_ids": [str(uuid4()) for _ in range(101)]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sub_issue_ids" in response.data

    @pytest.mark.django_db
    def test_partial_update_succeeds_for_child_work_item(
        self, session_client, workspace, project, default_state, completed_state
    ):
        """App PATCH must pass workspace_id so existing parents re-validate."""
        parent = Issue.objects.create(name="Parent", project=project, workspace=workspace, state=default_state)
        child = Issue.objects.create(
            name="Child",
            project=project,
            workspace=workspace,
            state=default_state,
            parent=parent,
        )

        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{child.id}/",
            {"state_id": str(completed_state.id), "name": "Child updated"},
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT, response.data
        child.refresh_from_db()
        assert child.state_id == completed_state.id
        assert child.name == "Child updated"
        assert child.parent_id == parent.id


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
    def test_legacy_children_url_uses_standard_contract(
        self, session_client, workspace, project, default_state, completed_state
    ):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        Issue.objects.create(
            name="Child 1", project=project, workspace=workspace, state=default_state, parent_id=epic_id
        )
        Issue.objects.create(
            name="Child 2", project=project, workspace=workspace, state=completed_state, parent_id=epic_id
        )

        response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/issues/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["sub_issues"]) == 2
        assert len(response.data["state_distribution"]["completed"]) == 1

    @pytest.mark.django_db
    def test_children_exclude_other_projects(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(
            session_client,
            workspace,
            project,
            state_id=str(default_state.id),
        ).data["id"]
        other_project = Project.objects.create(
            name="Other project",
            identifier="OTH",
            workspace=workspace,
            created_by=project.created_by,
        )
        other_state = State.objects.create(
            name="Other todo",
            group="unstarted",
            color="#fff",
            project=other_project,
            workspace=workspace,
        )
        Issue.objects.create(
            name="Cross-project child",
            project=other_project,
            workspace=workspace,
            state=other_state,
            parent_id=epic_id,
        )

        response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/issues/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["sub_issues"] == []

    @pytest.mark.django_db
    def test_attach_children_is_atomic_and_project_scoped(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project).data["id"]
        valid_child = Issue.objects.create(
            name="Valid child", project=project, workspace=workspace, state=default_state
        )
        other_project = Project.objects.create(
            name="Other project",
            identifier="OTH",
            workspace=workspace,
            created_by=project.created_by,
        )
        other_state = State.objects.create(
            name="Other todo", group="unstarted", color="#fff", project=other_project, workspace=workspace
        )
        foreign_child = Issue.objects.create(
            name="Foreign child", project=other_project, workspace=workspace, state=other_state
        )

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/issues/",
            {"sub_issue_ids": [str(valid_child.id), str(foreign_child.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        valid_child.refresh_from_db()
        foreign_child.refresh_from_db()
        assert valid_child.parent_id is None
        assert foreign_child.parent_id is None

    @pytest.mark.django_db
    def test_epic_subresources_reject_ordinary_issue(self, session_client, workspace, project, default_state):
        issue = Issue.objects.create(
            name="Ordinary work item",
            project=project,
            workspace=workspace,
            state=default_state,
        )
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{issue.id}/comments/",
            {"comment_html": "Must not be created"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
class TestEpicWebContracts:
    @pytest.mark.django_db
    def test_paginated_lists_count_only_epics(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        Issue.objects.create(name="Ordinary", project=project, workspace=workspace, state=default_state)

        for path in ("epics/", "v2/epics/"):
            response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/{path}")

            assert response.status_code == status.HTTP_200_OK, (path, response.data)
            count_key = "total_results" if path.startswith("v2/") else "total_count"
            assert response.data[count_key] == 1, (path, response.data)
            assert {str(item["id"]) for item in response.data["results"]} == {str(epic_id)}

    @pytest.mark.django_db
    def test_epic_collection_supports_grouped_web_response(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]

        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/",
            {"group_by": "state_id"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_count"] == 1
        state_group = response.data["results"][str(default_state.id)]
        assert state_group["total_results"] == 1
        assert {str(item["id"]) for item in state_group["results"]} == {str(epic_id)}

    @pytest.mark.django_db
    def test_bulk_list_returns_only_requested_epics(self, session_client, workspace, project, default_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(default_state.id)).data["id"]
        ordinary_issue = Issue.objects.create(
            name="Ordinary",
            project=project,
            workspace=workspace,
            state=default_state,
        )
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/list/",
            {"issues": f"{epic_id},{ordinary_issue.id}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert {str(item["id"]) for item in response.data} == {str(epic_id)}

    @pytest.mark.django_db
    def test_archive_round_trip(self, session_client, workspace, project, completed_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(completed_state.id)).data["id"]
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/archive/"
        assert session_client.post(url).status_code == status.HTTP_200_OK
        assert session_client.delete(url).status_code == status.HTTP_204_NO_CONTENT
        assert Issue.objects.get(pk=epic_id).archived_at is None

    @pytest.mark.django_db
    def test_epic_uses_standard_archive_surface(self, session_client, workspace, project, completed_state):
        enable_epics(session_client, workspace, project)
        epic_id = create_epic(session_client, workspace, project, state_id=str(completed_state.id)).data["id"]
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{epic_id}/archive/"

        assert session_client.post(url).status_code == status.HTTP_200_OK
        assert session_client.get(url).status_code == status.HTTP_200_OK
        assert session_client.delete(url).status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.django_db
    def test_epic_filters_do_not_mutate_work_item_filters(self, session_client, create_user, workspace, project):
        normal_property = ProjectUserProperty.objects.get(user=create_user, project=project)
        normal_property.display_filters = {"layout": "list"}
        normal_property.save(update_fields=["display_filters"])
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics-user-properties/"
        response = session_client.patch(url, {"display_filters": {"layout": "kanban"}}, format="json")
        assert response.status_code == status.HTTP_200_OK
        normal_property.refresh_from_db()
        assert normal_property.display_filters == {"layout": "list"}
        assert session_client.get(url).data["display_filters"] == {"layout": "kanban"}
