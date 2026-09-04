# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from importlib import import_module
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from django.apps import apps as django_apps
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueAssignee, Project, ProjectMember, State, WorkspaceMember
from plane.ext.models import (
    CapacityAuditEvent,
    GoogleCalendarCredential,
    TrainerCalendarSelection,
    TrainerProfile,
    WorkshopSchedule,
    WorkshopSession,
    WorkshopPlanDraft,
)
from plane.ext.capacity import GoogleCalendarError, decrypt_value, encrypt_value
from plane.ext.views import capacity as capacity_views
from plane.tests.factories import UserFactory
from plane.ext.services.issue_types import ensure_project_workshop_type

REQUIRED_CALENDAR_SCOPES = {
    "openid",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
}


def _mock_google_calendar_callback(monkeypatch, trainer, token):
    google_client = MagicMock()
    google_client.exchange_code.return_value = token
    google_client.userinfo.return_value = {
        "id": "google-subject",
        "email": "trainer@example.com",
        "verified_email": True,
    }
    google_client.list_calendars.return_value = [
        {"id": "trainer@example.com", "summary": "trainer@example.com", "primary": True, "access_role": "owner"}
    ]
    monkeypatch.setattr(capacity_views, "_google_client", lambda: (google_client, "client-id"))
    monkeypatch.setattr(
        capacity_views,
        "consume_oauth_transaction",
        lambda *_args: (
            {
                "workspace_slug": trainer.workspace.slug,
                "trainer_id": str(trainer.id),
                "host": "testserver",
                "code_verifier": "secret-code-verifier",
            },
            True,
        ),
    )
    return google_client


@pytest.mark.contract
@pytest.mark.django_db
def test_trainer_opt_in_requires_and_accepts_server_issued_csrf(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/trainers/me/"

    rejected = client.post(url)

    assert rejected.status_code == status.HTTP_403_FORBIDDEN
    assert not TrainerProfile.objects.filter(workspace=workspace, user=create_user).exists()
    assert not CapacityAuditEvent.objects.filter(
        workspace_id=workspace.id,
        actor_id=create_user.id,
        action=CapacityAuditEvent.Action.TRAINER_ACTIVATED,
    ).exists()

    csrf_response = client.get("/auth/get-csrf-token/")
    accepted = client.post(url, HTTP_X_CSRFTOKEN=csrf_response.data["csrf_token"])

    assert accepted.status_code == status.HTTP_201_CREATED
    assert accepted.data["user_id"] == str(create_user.id)
    assert accepted.data["status"] == TrainerProfile.Status.ACTIVE
    assert accepted.data["weekly_schedule"] == {
        **{day: [{"start": "09:00", "end": "22:00"}] for day in ("mon", "tue", "wed", "thu", "fri")},
        "sat": [],
        "sun": [],
    }
    assert "exceptions" not in accepted.data
    assert TrainerProfile.objects.filter(
        workspace=workspace,
        user=create_user,
        status=TrainerProfile.Status.ACTIVE,
    ).exists()
    assert CapacityAuditEvent.objects.filter(
        workspace_id=workspace.id,
        actor_id=create_user.id,
        action=CapacityAuditEvent.Action.TRAINER_ACTIVATED,
    ).exists()

    exception_response = client.patch(
        f"/api/workspaces/{workspace.slug}/capacity/trainers/{create_user.id}/schedule/",
        {"schedule_revision": accepted.data["schedule_revision"], "exceptions": []},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_response.data["csrf_token"],
    )

    assert exception_response.status_code == status.HTTP_400_BAD_REQUEST
    assert exception_response.data == {
        "error": "Schedule exceptions are no longer supported. Block that time in Google Calendar."
    }


@pytest.mark.contract
@pytest.mark.django_db
def test_booking_hours_migration_populates_only_empty_profiles(workspace, create_user):
    custom_user = UserFactory()
    empty_profile = TrainerProfile.objects.create(
        workspace=workspace,
        user=create_user,
        weekly_schedule={day: [] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        schedule_revision=3,
    )
    custom_schedule = {
        "mon": [{"start": "10:00", "end": "12:00"}],
        **{day: [] for day in ("tue", "wed", "thu", "fri", "sat", "sun")},
    }
    custom_profile = TrainerProfile.objects.create(
        workspace=workspace,
        user=custom_user,
        weekly_schedule=custom_schedule,
        schedule_revision=5,
    )
    migration = import_module("plane.ext.migrations.0021_booking_hours")

    migration.populate_empty_booking_hours(django_apps, None)

    empty_profile.refresh_from_db()
    custom_profile.refresh_from_db()
    assert empty_profile.weekly_schedule == migration.DEFAULT_WORKING_WEEK
    assert empty_profile.schedule_revision == 4
    assert custom_profile.weekly_schedule == custom_schedule
    assert custom_profile.schedule_revision == 5


@pytest.mark.contract
@pytest.mark.django_db
def test_workshop_session_migration_preserves_existing_schedule(workspace, create_user):
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=create_user)
    state = State.objects.create(
        name="Backlog", color="#000000", group="backlog", project=project, workspace=workspace, sequence=1000
    )
    workshop_type = ensure_project_workshop_type(project)
    issue = Issue.objects.create(
        name="Existing workshop",
        project=project,
        workspace=workspace,
        state=state,
        type=workshop_type,
        created_by=create_user,
    )
    IssueAssignee.objects.create(issue=issue, assignee=create_user, project=project, workspace=workspace)
    schedule = WorkshopSchedule.objects.create(
        issue=issue,
        starts_at="2026-09-07T09:00:00+02:00",
        ends_at="2026-09-07T13:00:00+02:00",
        preparation_minutes=30,
        travel_before_minutes=60,
        travel_after_minutes=45,
    )
    migration = import_module("plane.ext.migrations.0022_workshop_sessions")

    migration.backfill_workshop_sessions(django_apps, None)

    schedule.refresh_from_db()
    session = WorkshopSession.objects.get(schedule=schedule)
    assert session.starts_at == schedule.starts_at
    assert session.ends_at == schedule.ends_at
    assert session.preparation_minutes == 30
    assert session.travel_before_minutes == 60
    assert session.travel_after_minutes == 45
    assert list(session.trainers.values_list("id", flat=True)) == [create_user.id]


@pytest.mark.contract
@pytest.mark.django_db
def test_workshop_schedule_replaces_multiple_sessions_atomically(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    second_trainer = UserFactory()
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    state = State.objects.create(
        name="Backlog", color="#000000", group="backlog", project=project, workspace=workspace, sequence=1000
    )
    workshop_type = ensure_project_workshop_type(project)
    issue = Issue.objects.create(
        name="NetSec", project=project, workspace=workspace, state=state, type=workshop_type, created_by=create_user
    )
    for trainer in (create_user, second_trainer):
        TrainerProfile.objects.create(workspace=workspace, user=trainer)
        IssueAssignee.objects.create(issue=issue, assignee=trainer, project=project, workspace=workspace)

    client = APIClient(enforce_csrf_checks=True)
    client.force_login(create_user)
    csrf = client.get("/auth/get-csrf-token/").data["csrf_token"]
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/"
    payload = {
        "sessions": [
            {
                "starts_at": "2026-09-07T09:00:00+02:00",
                "ends_at": "2026-09-07T13:00:00+02:00",
                "preparation_minutes": 30,
                "travel_before_minutes": 60,
                "travel_after_minutes": 60,
                "trainer_ids": [str(create_user.id), str(second_trainer.id)],
            },
            {
                "starts_at": "2026-09-08T10:00:00+02:00",
                "ends_at": "2026-09-08T12:00:00+02:00",
                "preparation_minutes": 15,
                "travel_before_minutes": 0,
                "travel_after_minutes": 0,
                "trainer_ids": [str(second_trainer.id)],
            },
        ]
    }

    response = client.put(url, payload, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["sessions"]) == 2
    assert response.data["sessions"][1]["trainer_ids"] == [str(second_trainer.id)]
    schedule = WorkshopSchedule.objects.get(issue=issue)
    assert schedule.sessions.count() == 2
    assert set(schedule.sessions.get(position=0).trainers.values_list("id", flat=True)) == {
        create_user.id,
        second_trainer.id,
    }
    assert CapacityAuditEvent.objects.filter(
        issue_id=issue.id,
        action=CapacityAuditEvent.Action.WORKSHOP_UPDATED,
        metadata={"session_count": 2},
    ).exists()

    replacement = {"sessions": [payload["sessions"][1]]}
    replaced = client.put(url, replacement, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert replaced.status_code == status.HTTP_200_OK
    assert WorkshopSession.objects.filter(schedule=schedule).count() == 1
    assert replaced.data["sessions"][0]["starts_at"] == "2026-09-08T08:00:00+00:00"


@pytest.mark.contract
@pytest.mark.django_db
def test_workshop_session_rejects_a_trainer_who_is_not_an_assignee(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    outsider = UserFactory()
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    state = State.objects.create(
        name="Backlog", color="#000000", group="backlog", project=project, workspace=workspace, sequence=1000
    )
    workshop_type = ensure_project_workshop_type(project)
    issue = Issue.objects.create(
        name="NetSec", project=project, workspace=workspace, state=state, type=workshop_type, created_by=create_user
    )
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    TrainerProfile.objects.create(workspace=workspace, user=outsider)
    IssueAssignee.objects.create(issue=issue, assignee=create_user, project=project, workspace=workspace)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(create_user)
    csrf = client.get("/auth/get-csrf-token/").data["csrf_token"]

    response = client.put(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/workshop-schedule/",
        {
            "sessions": [
                {
                    "starts_at": "2026-09-07T09:00:00+02:00",
                    "ends_at": "2026-09-07T13:00:00+02:00",
                    "trainer_ids": [str(outsider.id)],
                }
            ]
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {"error": "Every trainer in session 1 must be an active Workshop assignee."}
    assert not WorkshopSchedule.objects.filter(issue=issue).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_workshop_plan_drafts_are_private_and_revision_protected(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    payload = {
        "title": "NetSec workshop",
        "duration_minutes": 240,
        "preparation_minutes": 30,
        "travel_before_minutes": 60,
        "travel_after_minutes": 60,
        "window_starts_at": "2026-09-07T00:00:00+02:00",
        "window_ends_at": "2026-09-14T00:00:00+02:00",
        "trainer_ids": [str(create_user.id)],
    }
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(create_user)
    csrf = client.get("/auth/get-csrf-token/").data["csrf_token"]
    collection_url = f"/api/workspaces/{workspace.slug}/capacity/plans/"

    created = client.post(collection_url, payload, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["title"] == "NetSec workshop"
    assert created.data["revision"] == 1
    detail_url = f"{collection_url}{created.data['id']}/"
    stale = client.put(detail_url, {**payload, "revision": 0}, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert stale.status_code == status.HTTP_409_CONFLICT
    assert stale.data["revision"] == 1

    outsider = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
    outsider_client = APIClient(enforce_csrf_checks=True)
    outsider_client.force_login(outsider)
    outsider_csrf = outsider_client.get("/auth/get-csrf-token/").data["csrf_token"]
    assert outsider_client.get(collection_url).data == {"results": []}
    assert (
        outsider_client.put(
            detail_url, {**payload, "revision": 1}, format="json", HTTP_X_CSRFTOKEN=outsider_csrf
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert WorkshopPlanDraft.objects.filter(owner=create_user, workspace=workspace).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "email_scope",
    [
        "email",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
)
def test_google_calendar_callback_accepts_email_scope_aliases(
    settings, workspace, create_user, monkeypatch, email_scope
):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    granted = REQUIRED_CALENDAR_SCOPES | {email_scope}
    google_client = _mock_google_calendar_callback(
        monkeypatch,
        trainer,
        {
            "access_token": "secret-access-token",
            "refresh_token": "secret-refresh-token",
            "scope": " ".join(sorted(granted)),
        },
    )
    client = APIClient()
    client.force_login(create_user)

    response = client.get("/auth/google/calendar/callback/?state=state&code=secret-authorization-code")

    assert response.status_code == status.HTTP_302_FOUND
    assert response.url == f"/{workspace.slug}/capacity?google=connected"
    google_client.userinfo.assert_called_once_with("secret-access-token")
    credential = GoogleCalendarCredential.objects.get(user=create_user, google_subject="google-subject")
    assert set(credential.granted_scopes) == granted
    selection = TrainerCalendarSelection.objects.get(trainer=trainer, credential=credential)
    assert [decrypt_value(value, credential.encryption_key_id) for value in selection.encrypted_calendar_ids] == [
        "trainer@example.com"
    ]
    assert selection.calendar_id_hashes == [TrainerCalendarSelection.calendar_hash("trainer@example.com")]
    assert CapacityAuditEvent.objects.filter(
        workspace_id=workspace.id,
        actor_id=create_user.id,
        trainer_id=create_user.id,
        action=CapacityAuditEvent.Action.GOOGLE_CONNECTED,
    ).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_google_calendar_callback_rejects_missing_email_scope_without_logging_secrets(
    settings, workspace, create_user, monkeypatch, caplog
):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    google_client = _mock_google_calendar_callback(
        monkeypatch,
        trainer,
        {
            "access_token": "secret-access-token",
            "refresh_token": "secret-refresh-token",
            "scope": " ".join(sorted(REQUIRED_CALENDAR_SCOPES)),
        },
    )
    client = APIClient()
    client.force_login(create_user)

    with caplog.at_level(logging.WARNING, logger=capacity_views.__name__):
        response = client.get("/auth/google/calendar/callback/?state=state&code=secret-authorization-code")

    assert response.status_code == status.HTTP_302_FOUND
    assert response.url == f"/{workspace.slug}/capacity?google=failed"
    google_client.userinfo.assert_not_called()
    assert not GoogleCalendarCredential.objects.exists()
    assert not TrainerCalendarSelection.objects.exists()
    assert not CapacityAuditEvent.objects.filter(action=CapacityAuditEvent.Action.GOOGLE_CONNECTED).exists()
    record = caplog.records[-1]
    assert record.error_code == "missing_scopes"
    assert "secret-authorization-code" not in caplog.text
    assert "secret-access-token" not in caplog.text
    assert "secret-refresh-token" not in caplog.text
    assert "secret-code-verifier" not in caplog.text


@pytest.mark.contract
@pytest.mark.django_db
def test_google_calendar_callback_logs_malformed_token_response(settings, workspace, create_user, monkeypatch, caplog):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    _mock_google_calendar_callback(
        monkeypatch,
        trainer,
        {
            "refresh_token": "secret-refresh-token",
            "scope": " ".join(sorted(REQUIRED_CALENDAR_SCOPES | {"email"})),
        },
    )
    client = APIClient()
    client.force_login(create_user)

    with caplog.at_level(logging.WARNING, logger=capacity_views.__name__):
        response = client.get("/auth/google/calendar/callback/?state=state&code=secret-authorization-code")

    assert response.status_code == status.HTTP_302_FOUND
    assert response.url == f"/{workspace.slug}/capacity?google=failed"
    record = caplog.records[-1]
    assert record.error_code == "invalid_token_response"
    assert "secret-authorization-code" not in caplog.text
    assert "secret-refresh-token" not in caplog.text


@pytest.mark.contract
@pytest.mark.django_db
def test_google_calendar_callback_preserves_existing_calendar_selection(settings, workspace, create_user, monkeypatch):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    encrypted_refresh, key_id = encrypt_value("existing-refresh-token")
    credential = GoogleCalendarCredential.objects.create(
        user=create_user,
        google_subject="google-subject",
        encrypted_refresh_token=encrypted_refresh,
        encryption_key_id=key_id,
    )
    encrypted_calendar, calendar_key_id = encrypt_value("private-calendar")
    assert calendar_key_id == key_id
    selection = TrainerCalendarSelection.objects.create(
        trainer=trainer,
        credential=credential,
        encrypted_calendar_ids=[encrypted_calendar],
        calendar_id_hashes=[TrainerCalendarSelection.calendar_hash("private-calendar")],
    )
    google_client = _mock_google_calendar_callback(
        monkeypatch,
        trainer,
        {
            "access_token": "secret-access-token",
            "scope": " ".join(sorted(REQUIRED_CALENDAR_SCOPES | {"email"})),
        },
    )
    client = APIClient()
    client.force_login(create_user)

    response = client.get("/auth/google/calendar/callback/?state=state&code=secret-authorization-code")

    assert response.url == f"/{workspace.slug}/capacity?google=connected"
    selection.refresh_from_db()
    assert [
        decrypt_value(value, selection.credential.encryption_key_id) for value in selection.encrypted_calendar_ids
    ] == ["private-calendar"]
    google_client.list_calendars.assert_not_called()


@pytest.mark.contract
@pytest.mark.django_db
def test_google_calendar_callback_keeps_connection_when_primary_autoselect_fails(
    settings, workspace, create_user, monkeypatch, caplog
):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    google_client = _mock_google_calendar_callback(
        monkeypatch,
        trainer,
        {
            "access_token": "secret-access-token",
            "refresh_token": "secret-refresh-token",
            "scope": " ".join(sorted(REQUIRED_CALENDAR_SCOPES | {"email"})),
        },
    )
    google_client.list_calendars.side_effect = GoogleCalendarError("provider_unavailable")
    client = APIClient()
    client.force_login(create_user)

    with caplog.at_level(logging.WARNING, logger=capacity_views.__name__):
        response = client.get("/auth/google/calendar/callback/?state=state&code=secret-authorization-code")

    assert response.url == f"/{workspace.slug}/capacity?google=connected"
    assert TrainerCalendarSelection.objects.get(trainer=trainer).calendar_id_hashes == []
    assert caplog.records[-1].error_code == "primary_calendar_autoselect_failed"
