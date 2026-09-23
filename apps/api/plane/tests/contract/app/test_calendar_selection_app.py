# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which of a trainer's calendars may block their time.

A shared training calendar carries everybody's training, so a trainer who picks
it as a blocking calendar blocks their own week with other people's workshops.
Their own trainings are already blocked by recognition, from their own
invitations, so the calendar is marked and refused rather than explained after
the fact.
"""

from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from rest_framework import status
from rest_framework.test import APIClient

from plane.ext.capacity.crypto import encrypt_value
from plane.ext.models import (
    GoogleCalendarCredential,
    GoogleTrainingRule,
    TrainerCalendarSelection,
    TrainerProfile,
)
from plane.ext.views import capacity as capacity_views

TRAINING_CALENDAR = "training@group.calendar.example"
OWN_CALENDAR = "trainer@example.com"


@pytest.fixture
def capacity(settings):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    return settings


def _connected(workspace, user):
    trainer = TrainerProfile.objects.create(workspace=workspace, user=user)
    encrypted, key_id = encrypt_value("refresh-token")
    credential = GoogleCalendarCredential.objects.create(
        user=user, google_subject="subject", encrypted_refresh_token=encrypted, encryption_key_id=key_id
    )
    return TrainerCalendarSelection.objects.create(trainer=trainer, credential=credential)


def _rule(workspace):
    encrypted, key_id = encrypt_value(TRAINING_CALENDAR)
    return GoogleTrainingRule.objects.create(
        workspace=workspace, label="Shared training calendar", encrypted_calendar_id=encrypted, encryption_key_id=key_id
    )


def _google(monkeypatch):
    client = MagicMock()
    client.list_calendars.return_value = [
        {"id": OWN_CALENDAR, "summary": OWN_CALENDAR, "primary": True, "access_role": "owner"},
        {"id": TRAINING_CALENDAR, "summary": "Training", "primary": False, "access_role": "reader"},
    ]
    monkeypatch.setattr(capacity_views, "_google_client", lambda: (client, "client-id"))
    return client


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


@pytest.mark.contract
@pytest.mark.django_db
def test_the_training_calendar_is_marked_in_the_listing(capacity, workspace, create_user, monkeypatch):
    _connected(workspace, create_user)
    _rule(workspace)
    _google(monkeypatch)
    client, _ = _client(create_user)

    response = client.get(f"/api/workspaces/{workspace.slug}/capacity/google/calendars/")

    marked = {item["id"]: item["is_training_calendar"] for item in response.data["calendars"]}
    assert marked == {OWN_CALENDAR: False, TRAINING_CALENDAR: True}


@pytest.mark.contract
@pytest.mark.django_db
def test_the_training_calendar_cannot_be_chosen_as_blocking(capacity, workspace, create_user, monkeypatch):
    """Otherwise every training the company runs would block this trainer's week."""
    selection = _connected(workspace, create_user)
    _rule(workspace)
    _google(monkeypatch)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/capacity/google/calendars/",
        {"calendar_ids": [OWN_CALENDAR, TRAINING_CALENDAR], "selection_revision": selection.revision},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "training_calendar_not_blocking"
    selection.refresh_from_db()
    assert selection.calendar_id_hashes == []


@pytest.mark.contract
@pytest.mark.django_db
def test_the_trainers_own_calendar_is_still_accepted(capacity, workspace, create_user, monkeypatch):
    selection = _connected(workspace, create_user)
    _rule(workspace)
    _google(monkeypatch)
    client, csrf = _client(create_user)

    response = client.put(
        f"/api/workspaces/{workspace.slug}/capacity/google/calendars/",
        {"calendar_ids": [OWN_CALENDAR], "selection_revision": selection.revision},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_200_OK
    selection.refresh_from_db()
    assert selection.calendar_id_hashes == [TrainerCalendarSelection.calendar_hash(OWN_CALENDAR)]
