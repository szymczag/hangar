# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Worklog activity stays with the people who may read worklogs (S20).

Logging time writes an `IssueActivity` row with `field="worklog"` and the logged
duration as its value. The work item's own activity feed already leaves it out
for guests (`test_worklog_app.py`). These tests cover the other surfaces that
list activity of every kind: a user's profile feed and its CSV export, the
public API's activity list and detail, and the notifications sent to the work
item's subscribers. Each was returning the row, duration included, to a project
guest.
"""

import json
from uuid import uuid4

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import status
from rest_framework.test import APIClient

from plane.app.serializers import IssueActivitySerializer
from plane.bgtasks.notification_task import notifications
from plane.db.models import (
    APIToken,
    Issue,
    IssueActivity,
    IssueSubscriber,
    Notification,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)

GUEST, MEMBER, ADMIN = 5, 15, 20


@pytest.fixture
def project(db, workspace, create_user):
    # Guests see others' work items here, so what is asserted is the worklog
    # rule rather than work item visibility.
    project = Project.objects.create(
        name="Worklog Surfaces",
        identifier="WLS",
        workspace=workspace,
        created_by=create_user,
        is_time_tracking_enabled=True,
        guest_view_all_features=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=ADMIN, is_active=True)
    return project


@pytest.fixture
def issue(db, project, workspace):
    state = State.objects.create(
        name="Todo", group="unstarted", color="#fff", project=project, workspace=workspace, default=True
    )
    return Issue.objects.create(name="Timed work", project=project, workspace=workspace, state=state)


def make_user(workspace, project, role, workspace_role=None):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"user-{uid}@hangar.test", username=f"user_{uid}")
    WorkspaceMember.objects.create(
        workspace=workspace,
        member=user,
        role=workspace_role if workspace_role is not None else role,
        is_active=True,
    )
    ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def activities(workspace, project, issue, create_user):
    """A worklog row and a priority row, both by the project admin."""
    worklog = IssueActivity.objects.create(
        issue=issue,
        project=project,
        workspace=workspace,
        actor=create_user,
        field="worklog",
        verb="created",
        new_value="1h 30m",
        comment="logged time",
    )
    priority = IssueActivity.objects.create(
        issue=issue,
        project=project,
        workspace=workspace,
        actor=create_user,
        field="priority",
        verb="updated",
        new_value="urgent",
    )
    return worklog, priority


def profile_activity_ids(client, workspace, user_id):
    response = client.get(f"/api/workspaces/{workspace.slug}/user-activity/{user_id}/")
    assert response.status_code == status.HTTP_200_OK
    return {str(item["id"]) for item in response.data["results"]}


@pytest.mark.contract
class TestProfileActivity:
    @pytest.mark.django_db
    def test_a_guest_does_not_see_worklog_rows(self, workspace, project, create_user, activities):
        worklog, priority = activities
        guest = make_user(workspace, project, GUEST)

        ids = profile_activity_ids(client_for(guest), workspace, create_user.id)

        assert str(worklog.id) not in ids
        assert str(priority.id) in ids

    @pytest.mark.django_db
    @pytest.mark.parametrize("role", [MEMBER, ADMIN])
    def test_members_and_admins_see_worklog_rows(self, workspace, project, create_user, activities, role):
        worklog, priority = activities
        reader = make_user(workspace, project, role)

        ids = profile_activity_ids(client_for(reader), workspace, create_user.id)

        assert {str(worklog.id), str(priority.id)} <= ids

    @pytest.mark.django_db
    def test_a_workspace_admin_with_a_guest_project_role_sees_worklog_rows(
        self, workspace, project, create_user, activities
    ):
        worklog, _ = activities
        admin = make_user(workspace, project, GUEST, workspace_role=ADMIN)

        assert str(worklog.id) in profile_activity_ids(client_for(admin), workspace, create_user.id)

    @pytest.mark.django_db
    def test_the_csv_export_leaves_worklog_rows_out_for_a_project_guest(
        self, workspace, project, create_user, activities
    ):
        # A workspace member, so the export is allowed at all, who is a guest in
        # this project.
        guest = make_user(workspace, project, GUEST, workspace_role=MEMBER)
        date = activities[0].created_at.date().isoformat()

        response = client_for(guest).post(
            f"/api/workspaces/{workspace.slug}/user-activity/{create_user.id}/export/", {"date": date}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.content.decode()
        assert "urgent" in body
        assert "1h 30m" not in body
        assert "worklog" not in body


@pytest.mark.contract
class TestPublicApiActivity:
    def _client(self, user):
        token = APIToken.objects.create(user=user, label="worklog", token=f"token-{uuid4().hex}")
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=token.token)
        return client

    @pytest.mark.django_db
    def test_a_guest_does_not_list_worklog_rows(self, workspace, project, issue, activities):
        worklog, priority = activities
        guest = make_user(workspace, project, GUEST)

        response = self._client(guest).get(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/activities/"
        )

        assert response.status_code == status.HTTP_200_OK
        ids = {str(item["id"]) for item in response.data["results"]}
        assert str(worklog.id) not in ids
        assert str(priority.id) in ids

    @pytest.mark.django_db
    def test_a_guest_cannot_read_a_worklog_row_by_id(self, workspace, project, issue, activities):
        worklog, _ = activities
        guest = make_user(workspace, project, GUEST)

        response = self._client(guest).get(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/activities/{worklog.id}/"
        )

        assert "1h 30m" not in json.dumps(response.data, cls=DjangoJSONEncoder)

    @pytest.mark.django_db
    def test_a_member_lists_worklog_rows(self, workspace, project, issue, activities):
        worklog, _ = activities
        member = make_user(workspace, project, MEMBER)

        response = self._client(member).get(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/activities/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert str(worklog.id) in {str(item["id"]) for item in response.data["results"]}


@pytest.mark.contract
class TestWorklogNotifications:
    @pytest.mark.django_db
    def test_only_subscribers_who_read_worklogs_are_notified(self, workspace, project, issue, create_user, activities):
        worklog, _ = activities
        guest = make_user(workspace, project, GUEST)
        member = make_user(workspace, project, MEMBER)
        guest_admin = make_user(workspace, project, GUEST, workspace_role=ADMIN)
        for subscriber in (guest, member, guest_admin):
            IssueSubscriber.objects.create(issue=issue, project=project, workspace=workspace, subscriber=subscriber)

        notifications(
            type="worklog.activity.created",
            issue_id=str(issue.id),
            project_id=str(project.id),
            actor_id=str(create_user.id),
            subscriber=False,
            issue_activities_created=json.dumps(
                IssueActivitySerializer([worklog], many=True).data, cls=DjangoJSONEncoder
            ),
            requested_data=json.dumps({"duration": 90}),
            current_instance=None,
        )

        receivers = set(Notification.objects.filter(entity_identifier=issue.id).values_list("receiver_id", flat=True))
        assert member.id in receivers
        assert guest_admin.id in receivers
        assert guest.id not in receivers
