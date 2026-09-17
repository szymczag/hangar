# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Grouping the Work Items list by parent and by nearest Epic."""

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, User, WorkspaceMember
from plane.ext.services import EpicAncestor, ensure_project_system_types
from plane.utils.paginator import BasePaginator

LIST_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/"


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(name="Hierarchy", identifier="HIE", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20, is_active=True)
    State.objects.create(
        name="Todo", group="unstarted", color="#ff0000", project=project, workspace=workspace, default=True
    )
    return project


@pytest.fixture
def hierarchy(db, workspace, project, create_user):
    """Epic A > Task A1 > Subtask A1a, Epic A > Task A2, Epic B > Task B1, loose Task."""

    task_type, epic_type = ensure_project_system_types(project)

    def make(name, issue_type, parent=None, author=create_user):
        issue = Issue(name=name, project=project, workspace=workspace, type=issue_type, parent=parent)
        issue.save(created_by_id=author.id)
        return issue

    epic_a = make("Epic A", epic_type)
    epic_b = make("Epic B", epic_type)
    task_a1 = make("Task A1", task_type, epic_a)
    subtask = make("Subtask A1a", task_type, task_a1)
    task_a2 = make("Task A2", task_type, epic_a)
    task_b1 = make("Task B1", task_type, epic_b)
    loose = make("Loose task", task_type)
    return {
        "epic_a": epic_a,
        "epic_b": epic_b,
        "task_a1": task_a1,
        "subtask": subtask,
        "task_a2": task_a2,
        "task_b1": task_b1,
        "loose": loose,
        "make": make,
        "task_type": task_type,
    }


def group_names(results):
    return {group: {row["name"] for row in body["results"]} for group, body in results.items()}


def get_grouped(client, workspace, project, **params):
    response = client.get(
        LIST_URL.format(slug=workspace.slug, project_id=project.id),
        {"sub_issue": "true", "per_page": 100, **params},
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    return response.data


@pytest.mark.contract
class TestGroupByParent:
    @pytest.mark.django_db
    def test_groups_work_items_under_their_direct_parent(self, session_client, workspace, project, hierarchy):
        data = get_grouped(session_client, workspace, project, group_by="parent_id")

        groups = group_names(data["results"])
        assert groups[str(hierarchy["epic_a"].id)] == {"Task A1", "Task A2"}
        assert groups[str(hierarchy["task_a1"].id)] == {"Subtask A1a"}
        assert groups[str(hierarchy["epic_b"].id)] == {"Task B1"}
        assert groups["None"] == {"Epic A", "Epic B", "Loose task"}
        assert data["results"][str(hierarchy["epic_a"].id)]["total_results"] == 2
        assert all(row["parent_id"] is None for row in data["results"]["None"]["results"])


@pytest.mark.contract
class TestGroupByEpic:
    @pytest.mark.django_db
    def test_groups_every_descendant_under_its_nearest_epic(self, session_client, workspace, project, hierarchy):
        data = get_grouped(session_client, workspace, project, group_by="epic_id")

        groups = group_names(data["results"])
        epic_a, epic_b = str(hierarchy["epic_a"].id), str(hierarchy["epic_b"].id)
        assert groups[epic_a] == {"Epic A", "Task A1", "Subtask A1a", "Task A2"}
        assert groups[epic_b] == {"Epic B", "Task B1"}
        assert groups["None"] == {"Loose task"}
        assert data["results"][epic_a]["total_results"] == 4
        subtask_row = next(row for row in data["results"][epic_a]["results"] if row["name"] == "Subtask A1a")
        assert subtask_row["epic_id"] == hierarchy["epic_a"].id

    @pytest.mark.django_db
    def test_sub_groups_by_epic(self, session_client, workspace, project, hierarchy):
        data = get_grouped(session_client, workspace, project, group_by="state_id", sub_group_by="epic_id")

        (state_group,) = [body for body in data["results"].values() if body["total_results"]]
        sub_groups = group_names(state_group["results"])
        assert sub_groups[str(hierarchy["epic_b"].id)] == {"Epic B", "Task B1"}
        assert sub_groups["None"] == {"Loose task"}

    @pytest.mark.django_db
    def test_soft_deleted_epic_no_longer_groups_its_tasks(self, session_client, workspace, project, hierarchy):
        hierarchy["epic_b"].delete()

        data = get_grouped(session_client, workspace, project, group_by="epic_id")

        groups = group_names(data["results"])
        assert str(hierarchy["epic_b"].id) not in groups
        assert groups["None"] == {"Loose task", "Task B1"}

    @pytest.mark.django_db
    def test_ungrouped_list_does_not_compute_epic(self, session_client, workspace, project, hierarchy):
        url = LIST_URL.format(slug=workspace.slug, project_id=project.id)
        response = session_client.get(url, {"sub_issue": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert all("epic_id" not in row for row in response.data["results"])


@pytest.mark.contract
class TestHierarchyGroupFilters:
    """The filters a client sends to load more work items of one group."""

    def names(self, client, workspace, project, **params):
        url = LIST_URL.format(slug=workspace.slug, project_id=project.id)
        response = client.get(url, {"sub_issue": "true", **params})
        assert response.status_code == status.HTTP_200_OK, response.data
        return {row["name"] for row in response.data["results"]}

    @pytest.mark.django_db
    def test_parent_filter(self, session_client, workspace, project, hierarchy):
        epic_a = str(hierarchy["epic_a"].id)

        assert self.names(session_client, workspace, project, parent=epic_a) == {"Task A1", "Task A2"}
        assert self.names(session_client, workspace, project, parent="None") == {"Epic A", "Epic B", "Loose task"}

    @pytest.mark.django_db
    def test_epic_filter(self, session_client, workspace, project, hierarchy):
        epic_b = str(hierarchy["epic_b"].id)

        assert self.names(session_client, workspace, project, epic=str(hierarchy["epic_a"].id)) == {
            "Epic A",
            "Task A1",
            "Subtask A1a",
            "Task A2",
        }
        assert self.names(session_client, workspace, project, epic="None") == {"Loose task"}
        assert self.names(session_client, workspace, project, epic=f"None,{epic_b}") == {
            "Loose task",
            "Epic B",
            "Task B1",
        }

    @pytest.mark.django_db
    def test_invalid_identifiers_are_ignored(self, session_client, workspace, project, hierarchy):
        everything = self.names(session_client, workspace, project)

        assert self.names(session_client, workspace, project, parent="not-a-uuid") == everything
        assert self.names(session_client, workspace, project, epic="' OR 1=1 --") == everything


@pytest.mark.contract
class TestHierarchyGroupingBoundaries:
    @pytest.mark.django_db
    def test_unknown_group_field_is_still_rejected(self, session_client, workspace, project, hierarchy):
        response = session_client.get(
            LIST_URL.format(slug=workspace.slug, project_id=project.id), {"group_by": "parent__name"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_epic_grouping_requires_the_annotation(self, project, hierarchy):
        queryset = Issue.issue_objects.filter(project=project)

        assert BasePaginator._has_group_field(queryset, "epic_id") is False
        assert BasePaginator._has_group_field(queryset.annotate(epic_id=EpicAncestor()), "epic_id") is True
        assert BasePaginator._has_group_field(queryset, "parent_id") is True

    @pytest.mark.django_db
    def test_restricted_guest_groups_only_reference_visible_work_items(self, workspace, project, hierarchy):
        uid = uuid4().hex[:8]
        guest = User.objects.create(email=f"guest-{uid}@hangar.test", username=f"guest_{uid}")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
        ProjectMember.objects.create(project=project, member=guest, workspace=workspace, role=5, is_active=True)
        own_task = hierarchy["make"]("Guest task", hierarchy["task_type"], hierarchy["epic_a"], guest)
        client = APIClient()
        client.force_authenticate(user=guest)

        for field in ("parent_id", "epic_id"):
            data = get_grouped(client, workspace, project, group_by=field)

            assert set(data["results"]) == {str(hierarchy["epic_a"].id), "None"}
            rows = [row for body in data["results"].values() for row in body["results"]]
            assert [row["id"] for row in rows] == [own_task.id]
