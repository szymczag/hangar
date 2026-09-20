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
