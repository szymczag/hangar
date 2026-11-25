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


def store_notification(workspace, project, issue, receiver, actor, field, value):
    """A notification as the task writes it, stored before any role change."""
    return Notification.objects.create(
        workspace=workspace,
        project=project,
        receiver=receiver,
        triggered_by=actor,
        entity_identifier=issue.id,
        entity_name="issue",
        sender="in_app:issue_activities:subscribed",
        title="logged time" if field == "worklog" else "updated the priority to",
        data={
            "issue": {"id": str(issue.id), "name": issue.name, "identifier": project.identifier, "sequence_id": 1},
            "issue_activity": {"field": field, "verb": "created", "new_value": value, "old_value": ""},
        },
    )


@pytest.mark.contract
class TestStoredWorklogNotifications:
    """Rows stored before the fix, or while the receiver was still a project member."""

    def _setup(self, workspace, project, issue, create_user, role, workspace_role=None):
        receiver = make_user(workspace, project, role, workspace_role=workspace_role)
        worklog = store_notification(workspace, project, issue, receiver, create_user, "worklog", "1h 30m")
        priority = store_notification(workspace, project, issue, receiver, create_user, "priority", "urgent")
        # No activity data at all: must never be mistaken for a worklog row.
        bare = Notification.objects.create(
            workspace=workspace,
            project=project,
            receiver=receiver,
            entity_identifier=issue.id,
            entity_name="issue",
            sender="in_app:issue_activities:subscribed",
            title="",
            data=None,
        )
        return client_for(receiver), worklog, priority, bare

    def _list(self, client, workspace):
        response = client.get(f"/api/workspaces/{workspace.slug}/users/notifications/")
        assert response.status_code == status.HTTP_200_OK
        return response

    def _unread(self, client, workspace):
        response = client.get(f"/api/workspaces/{workspace.slug}/users/notifications/unread/")
        assert response.status_code == status.HTTP_200_OK
        return response.data["total_unread_notifications_count"]

    @pytest.mark.django_db
    def test_a_guest_neither_lists_nor_counts_a_stored_worklog_notification(
        self, workspace, project, issue, create_user
    ):
        client, worklog, priority, bare = self._setup(workspace, project, issue, create_user, GUEST)

        response = self._list(client, workspace)

        ids = {str(item["id"]) for item in response.data}
        assert str(worklog.id) not in ids
        assert {str(priority.id), str(bare.id)} <= ids
        assert "1h 30m" not in json.dumps(response.data, cls=DjangoJSONEncoder)
        assert self._unread(client, workspace) == 2

    @pytest.mark.django_db
    def test_a_member_demoted_to_guest_loses_the_stored_worklog_notification(
        self, workspace, project, issue, create_user
    ):
        client, worklog, _, _ = self._setup(workspace, project, issue, create_user, MEMBER)
        assert str(worklog.id) in {str(item["id"]) for item in self._list(client, workspace).data}

        ProjectMember.objects.filter(project=project, member=worklog.receiver).update(role=GUEST)

        assert str(worklog.id) not in {str(item["id"]) for item in self._list(client, workspace).data}

    @pytest.mark.django_db
    @pytest.mark.parametrize("suffix,method", [("", "get"), ("read/", "post"), ("archive/", "post")])
    def test_a_guest_cannot_reach_a_stored_worklog_notification_by_id(
        self, workspace, project, issue, create_user, suffix, method
    ):
        client, worklog, _, _ = self._setup(workspace, project, issue, create_user, GUEST)

        url = f"/api/workspaces/{workspace.slug}/users/notifications/{worklog.id}/{suffix}"
        response = getattr(client, method)(url)

        assert response.status_code != status.HTTP_200_OK
        assert "1h 30m" not in json.dumps(getattr(response, "data", None), cls=DjangoJSONEncoder)

    @pytest.mark.django_db
    @pytest.mark.parametrize("role,workspace_role", [(MEMBER, None), (ADMIN, None), (GUEST, ADMIN)])
    def test_readers_still_list_and_count_it(self, workspace, project, issue, create_user, role, workspace_role):
        client, worklog, _, _ = self._setup(workspace, project, issue, create_user, role, workspace_role)

        assert str(worklog.id) in {str(item["id"]) for item in self._list(client, workspace).data}
        assert self._unread(client, workspace) == 3
