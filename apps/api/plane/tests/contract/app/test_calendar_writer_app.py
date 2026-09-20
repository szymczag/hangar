# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Connecting the account that writes workshops into the shared calendar.

The coordinator who does this is not necessarily a trainer, which is the whole
reason this path exists separately: gating it on a trainer profile would lock
out exactly the person the feature is for.
"""

from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from plane.ext.views import capacity as capacity_views

from plane.db.models import WorkspaceMember
from plane.ext.capacity.crypto import encrypt_value
from plane.ext.models import GoogleCalendarCredential, GoogleTrainingRule

WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"


@pytest.fixture
def capacity(settings, monkeypatch):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    monkeypatch.setattr(capacity_views, "_google_client", lambda: (MagicMock(), "client-id"))
    return settings


def _rule(workspace):
    encrypted, key_id = encrypt_value("shared@example.test")
    return GoogleTrainingRule.objects.create(
        workspace=workspace,
        label="Shared training calendar",
        encrypted_calendar_id=encrypted,
        encryption_key_id=key_id,
    )


def _client(user):
    client = APIClient()
    client.force_login(user)
    return client


def _start(client, workspace, rule):
    return client.post(
        f"/api/workspaces/{workspace.slug}/capacity/google/start/",
        {"calendar_writer": True, "rule_id": str(rule.id)},
        format="json",
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_a_coordinator_who_is_not_a_trainer_can_start_the_writer_connection(capacity, workspace, create_user):
    """The reason this path is not the trainer path.

    No TrainerProfile exists for this user, and none should be needed: the
    person who keeps the training calendar is an administrator, not necessarily
    somebody who delivers training.
    """
    rule = _rule(workspace)
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=20)

    response = _start(_client(create_user), workspace, rule)

    assert response.status_code == 200
    query = parse_qs(urlparse(response.data["authorization_url"]).query)
    assert WRITE_SCOPE in query["scope"][0].split()


@pytest.mark.contract
@pytest.mark.django_db
def test_the_writer_connection_asks_for_no_reading_permissions(capacity, workspace, create_user):
    """Asking for what the feature does not exercise is the habit this refuses."""
    rule = _rule(workspace)
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=20)

    response = _start(_client(create_user), workspace, rule)

    scopes = set(parse_qs(urlparse(response.data["authorization_url"]).query)["scope"][0].split())
    assert not any(scope.endswith("calendar.events.freebusy") for scope in scopes)
    assert not any(scope.endswith("calendar.calendarlist.readonly") for scope in scopes)
    assert not any(scope.endswith("calendar.events.readonly") for scope in scopes)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_cannot_connect_a_writing_account(capacity, workspace, create_user):
    rule = _rule(workspace)
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=15)

    assert _start(_client(create_user), workspace, rule).status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_a_rule_in_another_workspace_is_not_writable_from_here(capacity, workspace, create_user, django_user_model):
    """The rule id comes from the request, so it is checked against the slug."""
    from plane.db.models import Workspace

    other = Workspace.objects.create(name="Other", slug="other-ws", owner=create_user)
    foreign_rule = _rule(other)
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=20)

    assert _start(_client(create_user), workspace, foreign_rule).status_code == 404


@pytest.mark.contract
@pytest.mark.django_db
def test_a_rule_reports_how_its_writer_is_doing(capacity, workspace, create_user):
    """An administrator must be able to tell these three apart.

    "Nothing connected", "the token died" and "the permission was withdrawn in
    Google" need different actions, and a single "not working" would send
    somebody to reconnect an account whose problem is consent.
    """
    rule = _rule(workspace)
    WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=20)
    client = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/google/training-rules/"

    assert client.get(url).data["results"][0]["writer_status"] == "not_connected"

    encrypted, key_id = encrypt_value("coordinator@example.test")
    credential = GoogleCalendarCredential.objects.create(
        user=create_user,
        google_subject="writer-subject",
        encrypted_refresh_token=encrypted,
        encrypted_google_email=encrypted,
        encryption_key_id=key_id,
        granted_scopes=[WRITE_SCOPE],
    )
    rule.writer_credential = credential
    rule.save(update_fields=["writer_credential"])
    row = client.get(url).data["results"][0]
    assert row["writer_status"] == "ok"
    assert row["writer_email"] == "coordinator@example.test"

    credential.granted_scopes = []
    credential.save(update_fields=["granted_scopes"])
    assert client.get(url).data["results"][0]["writer_status"] == "scope_missing"

    credential.granted_scopes = [WRITE_SCOPE]
    credential.status = GoogleCalendarCredential.Status.REAUTHORIZATION_REQUIRED
    credential.save(update_fields=["granted_scopes", "status"])
    assert client.get(url).data["results"][0]["writer_status"] == "reauthorization_required"


@pytest.mark.contract
@pytest.mark.django_db
def test_losing_the_writing_credential_leaves_the_rule_recognizing(capacity, workspace, create_user):
    """Reading a calendar never needed a writer, and must not start to."""
    rule = _rule(workspace)
    encrypted, key_id = encrypt_value("coordinator@example.test")
    credential = GoogleCalendarCredential.objects.create(
        user=create_user,
        google_subject="writer-subject",
        encrypted_refresh_token=encrypted,
        encrypted_google_email=encrypted,
        encryption_key_id=key_id,
        granted_scopes=[WRITE_SCOPE],
    )
    rule.writer_credential = credential
    rule.save(update_fields=["writer_credential"])

    # Hard, matching what disconnecting Google actually does. It has to be:
    # this application's ordinary delete is soft, and the database never runs
    # ON DELETE SET NULL for a row that is still there -- so a soft delete would
    # leave the rule pointing at a credential nobody can use.
    credential.delete(soft=False)
    rule.refresh_from_db()

    assert GoogleTrainingRule.objects.filter(id=rule.id).exists()
    assert rule.writer_credential is None
