# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueActivity, IssueComment, Project, ProjectMember, State, User, WorkspaceMember

from plane.ext.models import IssueWorkLog


@pytest.fixture(autouse=True)
def mock_issue_activity(mocker):
    """Keep API contract tests independent from the external Celery broker."""
    mocker.patch("plane.ext.views.worklog.issue_activity.delay")
    mocker.patch("plane.db.mixins.soft_delete_related_objects.delay")


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Worklog Project",
        identifier="WLG",
        workspace=workspace,
        created_by=create_user,
        is_time_tracking_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def state(db, project, workspace):
    return State.objects.create(
        name="Todo", group="unstarted", color="#fff", project=project, workspace=workspace, default=True
    )


@pytest.fixture
def issue(db, project, workspace, state):
    return Issue.objects.create(name="Timed work", project=project, workspace=workspace, state=state)


def worklogs_url(workspace, project, issue):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/worklogs/"


def make_role_client(workspace, project, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"user-{uid}@hangar.test", username=f"user_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.contract
class TestWorklogCRUD:
    @pytest.mark.django_db
    def test_create_and_total(self, session_client, workspace, project, issue, create_user):
        response = session_client.post(
            worklogs_url(workspace, project, issue), {"duration": 90, "description": "review"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["logged_by"] == create_user.id

        session_client.post(worklogs_url(workspace, project, issue), {"duration": 30}, format="json")
        listing = session_client.get(worklogs_url(workspace, project, issue))
        assert listing.status_code == status.HTTP_200_OK
        assert listing.data["total_duration"] == 120
        assert len(listing.data["worklogs"]) == 2

    @pytest.mark.django_db
    def test_logged_by_spoofing_ignored(self, session_client, workspace, project, issue, create_user):
        other = User.objects.create(email=f"o-{uuid4().hex[:8]}@hangar.test", username=f"o_{uuid4().hex[:8]}")
        response = session_client.post(
            worklogs_url(workspace, project, issue), {"duration": 10, "logged_by": str(other.id)}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert IssueWorkLog.objects.get(pk=response.data["id"]).logged_by_id == create_user.id

    @pytest.mark.django_db
    def test_duration_bounds(self, session_client, workspace, project, issue):
        for bad in (0, 24 * 60 + 1, -5):
            response = session_client.post(
                worklogs_url(workspace, project, issue), {"duration": bad}, format="json"
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST, bad

    @pytest.mark.django_db
    def test_description_length_is_bounded(self, session_client, workspace, project, issue):
        response = session_client.post(
            worklogs_url(workspace, project, issue),
            {"duration": 10, "description": "x" * 2001},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_disabled_flag_blocks(self, session_client, workspace, project, issue):
        project.is_time_tracking_enabled = False
        project.save()
        response = session_client.post(worklogs_url(workspace, project, issue), {"duration": 10}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_missing_issue_returns_not_found(self, session_client, workspace, project):
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{uuid4()}/worklogs/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_guest_cannot_log(self, workspace, project, issue):
        guest_client, _ = make_role_client(workspace, project, role=5)
        response = guest_client.post(worklogs_url(workspace, project, issue), {"duration": 10}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_guest_cannot_list_worklogs(self, workspace, project, issue):
        guest_client, _ = make_role_client(workspace, project, role=5)

        response = guest_client.get(worklogs_url(workspace, project, issue))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    @pytest.mark.parametrize("role", [15, 20])
    def test_member_and_admin_can_list_worklogs(self, workspace, project, issue, role):
        client, _ = make_role_client(workspace, project, role=role)

        response = client.get(worklogs_url(workspace, project, issue))

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.contract
class TestGuestWorklogActivityConfidentiality:
    @pytest.mark.django_db
    @pytest.mark.parametrize("query", ["", "?activity_type=issue-property", "?created_at__gt=2000-01-01T00:00:00Z"])
    def test_guest_history_omits_worklogs_but_keeps_other_activity_and_comments(
        self, workspace, project, issue, query
    ):
        guest_client, guest = make_role_client(workspace, project, role=5)
        worklog_activity = IssueActivity.objects.create(
            issue=issue,
            project=project,
            workspace=workspace,
            actor=guest,
            field="worklog",
            verb="created",
        )
        normal_activity = IssueActivity.objects.create(
            issue=issue,
            project=project,
            workspace=workspace,
            actor=guest,
            field="priority",
            verb="updated",
        )
        comment = IssueComment.objects.create(
            issue=issue,
            project=project,
            workspace=workspace,
            actor=guest,
            comment_html="<p>visible</p>",
            comment_stripped="visible",
        )

        response = guest_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/history/{query}"
        )

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {str(item["id"]) for item in response.data}
        assert str(worklog_activity.id) not in returned_ids
        assert str(normal_activity.id) in returned_ids
        if "activity_type=issue-property" not in query:
            assert str(comment.id) in returned_ids


@pytest.mark.contract
class TestWorklogOwnership:
    @pytest.mark.django_db
    def test_member_cannot_edit_others_entry(self, session_client, workspace, project, issue):
        created = session_client.post(
            worklogs_url(workspace, project, issue), {"duration": 60}, format="json"
        ).data
        member_client, _ = make_role_client(workspace, project, role=15)
        response = member_client.patch(
            f"{worklogs_url(workspace, project, issue)}{created['id']}/", {"duration": 5}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_author_can_edit_own_entry(self, workspace, project, issue):
        member_client, _ = make_role_client(workspace, project, role=15)
        created = member_client.post(
            worklogs_url(workspace, project, issue), {"duration": 60}, format="json"
        ).data
        response = member_client.patch(
            f"{worklogs_url(workspace, project, issue)}{created['id']}/", {"duration": 45}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["duration"] == 45

    @pytest.mark.django_db
    def test_admin_can_delete_any_entry(self, session_client, workspace, project, issue):
        member_client, _ = make_role_client(workspace, project, role=15)
        created = member_client.post(
            worklogs_url(workspace, project, issue), {"duration": 60}, format="json"
        ).data
        response = session_client.delete(f"{worklogs_url(workspace, project, issue)}{created['id']}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueWorkLog.objects.filter(pk=created["id"]).exists()

    @pytest.mark.django_db
    def test_workspace_admin_can_delete_any_entry(self, workspace, project, issue):
        member_client, _ = make_role_client(workspace, project, role=15)
        created = member_client.post(
            worklogs_url(workspace, project, issue), {"duration": 60}, format="json"
        ).data
        admin_client, admin = make_role_client(workspace, project, role=15)
        WorkspaceMember.objects.filter(workspace=workspace, member=admin).update(role=20)

        response = admin_client.delete(f"{worklogs_url(workspace, project, issue)}{created['id']}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.django_db
    def test_disabled_flag_blocks_detail_mutations(self, session_client, workspace, project, issue):
        created = session_client.post(
            worklogs_url(workspace, project, issue), {"duration": 60}, format="json"
        ).data
        project.is_time_tracking_enabled = False
        project.save(update_fields=["is_time_tracking_enabled"])

        detail_url = f"{worklogs_url(workspace, project, issue)}{created['id']}/"
        patch_response = session_client.patch(detail_url, {"duration": 5}, format="json")
        delete_response = session_client.delete(detail_url)

        assert patch_response.status_code == status.HTTP_400_BAD_REQUEST
        assert delete_response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueWorkLog.objects.filter(pk=created["id"], duration=60).exists()

    @pytest.mark.django_db
    def test_missing_worklog_returns_not_found(self, session_client, workspace, project, issue):
        response = session_client.patch(
            f"{worklogs_url(workspace, project, issue)}{uuid4()}/",
            {"duration": 5},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_cross_project_scoping(self, session_client, workspace, project, issue, create_user):
        created = session_client.post(
            worklogs_url(workspace, project, issue), {"duration": 60}, format="json"
        ).data
        # Same workspace, different project — the entry must not be reachable
        other_project = Project.objects.create(
            name="Other", identifier="OTW", workspace=workspace, created_by=create_user,
            is_time_tracking_enabled=True,
        )
        ProjectMember.objects.create(project=other_project, member=create_user, role=20, is_active=True)
        response = session_client.delete(
            f"/api/workspaces/{workspace.slug}/projects/{other_project.id}/issues/{issue.id}/worklogs/{created['id']}/"
        )
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
        assert IssueWorkLog.objects.filter(pk=created["id"]).exists()
