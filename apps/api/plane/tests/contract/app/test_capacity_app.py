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

from plane.ext.models import (
    CapacityAuditEvent,
    GoogleCalendarCredential,
    TrainerCalendarSelection,
    TrainerProfile,
)
from plane.ext.capacity import GoogleCalendarError, decrypt_value, encrypt_value
from plane.ext.views import capacity as capacity_views
from plane.tests.factories import UserFactory

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
