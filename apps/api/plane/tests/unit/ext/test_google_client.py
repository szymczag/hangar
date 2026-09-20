# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The seam between the Google client and the hardened outbound transport.

Every other capacity test mocks `GoogleCalendarClient` itself, which is right
for testing what the capacity code does with an answer -- and is exactly why a
call that could never reach Google shipped: nothing exercised the client against
the object the transport actually returns.

`fetch_validated` answers with `OutboundResponse`, not a `requests.Response`.
They are not interchangeable, and the difference is invisible to a mock.
"""

import uuid
from datetime import datetime, timezone

import pytest

from plane.authentication.utils.outbound import OutboundResponse
from plane.ext.capacity import google as google_module
from plane.ext.capacity.google import GoogleCalendarClient


class _Credential:
    """Enough of a credential for the call; the status write matches no row."""

    pk = uuid.uuid4()


class _Client(GoogleCalendarClient):
    def access_token(self, credential, force=False):
        return "token"


@pytest.fixture
def client():
    return _Client(client_id="id", client_secret="secret")


@pytest.mark.django_db
def test_a_json_answer_is_parsed(client, monkeypatch):
    monkeypatch.setattr(
        google_module, "_request", lambda *args, **kwargs: OutboundResponse(200, b'{"items": [{"id": "one"}]}')
    )

    payload = client._authorized_json(_Credential(), "GET", "https://www.googleapis.com/calendar/v3/x")

    assert payload == {"items": [{"id": "one"}]}


@pytest.mark.django_db
def test_an_empty_body_is_not_parsed_as_json(client, monkeypatch):
    """`events.delete` answers 204 with nothing in it.

    Parsing that raises, which this method would report as
    `provider_unavailable` -- so a delete that worked would be retried forever
    against an event that is already gone.
    """
    monkeypatch.setattr(google_module, "_request", lambda *args, **kwargs: OutboundResponse(204, b""))

    assert client._authorized_json(_Credential(), "DELETE", "https://www.googleapis.com/calendar/v3/x") == {}


@pytest.mark.django_db
def test_a_body_is_ignored_when_none_was_expected(client, monkeypatch):
    monkeypatch.setattr(google_module, "_request", lambda *args, **kwargs: OutboundResponse(200, b'{"ignored": true}'))

    result = client._authorized_json(
        _Credential(), "DELETE", "https://www.googleapis.com/calendar/v3/x", expect_json=False
    )

    assert result == {}


@pytest.mark.django_db
def test_an_unexpected_failure_degrades_the_ledger_instead_of_raising(workspace, create_user, settings, monkeypatch):
    """A defect in this module must not take the capacity ledger down with it.

    This subsystem's rule runs the other way round: a read that failed has to
    read as unverified, which refuses a booking rather than permitting one. A
    traceback escaping to the view refuses nothing and breaks the screen for
    everybody, which is how rc.62 shipped a 500 on every capacity request.
    """
    from cryptography.fernet import Fernet

    from plane.ext.capacity import calculation
    from plane.ext.capacity.crypto import encrypt_value
    from plane.ext.models import GoogleCalendarCredential, TrainerCalendarSelection, TrainerProfile

    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    encrypted, key_id = encrypt_value("trainer@example.test")
    credential = GoogleCalendarCredential.objects.create(
        user=create_user,
        google_subject="degrade-test",
        encrypted_refresh_token=encrypted,
        encrypted_google_email=encrypted,
        encryption_key_id=key_id,
    )
    selection = TrainerCalendarSelection.objects.create(trainer=trainer, credential=credential)
    selection.encrypted_calendar_ids = [encrypt_value("primary")[0]]
    selection.save()

    class _Exploding:
        def list_calendars(self, *args, **kwargs):
            raise AttributeError("the exact shape of the rc.62 defect")

        def freebusy(self, *args, **kwargs):
            raise AttributeError("the exact shape of the rc.62 defect")

    monkeypatch.setattr(calculation, "_google_client", lambda: _Exploding())

    busy, connection, freshness = calculation._google_busy(
        trainer, datetime(2026, 9, 14, tzinfo=timezone.utc), datetime(2026, 9, 21, tzinfo=timezone.utc), force=True
    )

    assert busy == []
    # Not "fresh", which is the only value `booking_preflight` accepts, so the
    # booking path refuses rather than treating an unreadable week as free.
    assert freshness == "provider_error"
    assert connection == "provider_error"
