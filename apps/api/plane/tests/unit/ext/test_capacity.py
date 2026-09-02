# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import ValidationError

from plane.ext.capacity import calculation
from plane.ext.capacity.calculation import _google_busy, _intersections, _merge, _minutes, _subtract
from plane.ext.capacity.crypto import decrypt_value, encrypt_value
from plane.ext.capacity.schedules import validate_intervals, validate_weekly_schedule
from plane.ext.models import GoogleCalendarCredential


def test_calendar_credential_round_trip_and_key_rotation(settings):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (old_key,)
    encrypted, key_id = encrypt_value("refresh-token")

    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (new_key, old_key)

    assert decrypt_value(encrypted, key_id) == "refresh-token"
    rotated, rotated_key_id = encrypt_value(decrypt_value(encrypted, key_id))
    assert rotated_key_id != key_id
    assert decrypt_value(rotated, rotated_key_id) == "refresh-token"


def test_calendar_credential_configuration_fails_closed(settings):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = ()

    with pytest.raises(ImproperlyConfigured):
        encrypt_value("refresh-token")


def test_schedule_validation_normalizes_and_rejects_overlap():
    assert validate_intervals([{"start": "13:00", "end": "17:00"}, {"start": "09:00", "end": "12:00"}]) == [
        {"start": "09:00", "end": "12:00"},
        {"start": "13:00", "end": "17:00"},
    ]

    with pytest.raises(ValidationError, match="may not overlap"):
        validate_intervals([{"start": "09:00", "end": "12:00"}, {"start": "11:00", "end": "13:00"}])


def test_weekly_schedule_requires_every_day():
    with pytest.raises(ValidationError, match="exactly"):
        validate_weekly_schedule({"mon": []})


def test_capacity_interval_math_unions_before_subtraction():
    point = datetime(2026, 9, 7, 8, tzinfo=timezone.utc)
    hour = 60 * 60
    intervals = _merge(
        [
            (point, datetime.fromtimestamp(point.timestamp() + 3 * hour, tz=timezone.utc)),
            (
                datetime.fromtimestamp(point.timestamp() + 2 * hour, tz=timezone.utc),
                datetime.fromtimestamp(point.timestamp() + 5 * hour, tz=timezone.utc),
            ),
        ]
    )

    assert _minutes(intervals) == 300
    assert (
        _minutes(
            _intersections(
                intervals,
                [
                    (
                        datetime.fromtimestamp(point.timestamp() + hour, tz=timezone.utc),
                        datetime.fromtimestamp(point.timestamp() + 4 * hour, tz=timezone.utc),
                    )
                ],
            )
        )
        == 180
    )
    assert (
        _minutes(
            _subtract(
                intervals,
                [(point, datetime.fromtimestamp(point.timestamp() + hour, tz=timezone.utc))],
            )
        )
        == 240
    )


def test_google_busy_normalizes_provider_window_and_clips_result(monkeypatch):
    start = datetime(2026, 9, 7, 8, 7, tzinfo=timezone.utc)
    end = datetime(2026, 9, 7, 9, 8, tzinfo=timezone.utc)
    credential = SimpleNamespace(
        status=GoogleCalendarCredential.Status.CONNECTED,
        Status=GoogleCalendarCredential.Status,
        encryption_key_id="key",
    )
    selection = SimpleNamespace(
        id="selection-id",
        revision=2,
        credential=credential,
        encrypted_calendar_ids=["encrypted"],
    )
    trainer = SimpleNamespace(id="trainer-id", calendar_selection=selection)
    client = MagicMock()
    client.freebusy.return_value = [
        {
            "start": (start - timedelta(minutes=7)).isoformat(),
            "end": (end + timedelta(minutes=7)).isoformat(),
        }
    ]
    monkeypatch.setattr(calculation, "decrypt_value", lambda *_args: "calendar-id")
    monkeypatch.setattr(calculation, "_google_client", lambda: client)
    monkeypatch.setattr(calculation.cache, "get", lambda _key: None)
    monkeypatch.setattr(calculation.cache, "set", MagicMock())
    monkeypatch.setattr(calculation, "register_busy_cache_key", MagicMock())

    intervals, connection_status, availability_status = _google_busy(trainer, start, end)

    assert intervals == [(start, end)]
    assert connection_status == "connected"
    assert availability_status == "fresh"
    client.freebusy.assert_called_once_with(
        credential,
        ["calendar-id"],
        time_min="2026-09-07T08:00:00Z",
        time_max="2026-09-07T09:15:00Z",
    )


def test_google_disconnect_revocation_treats_invalid_token_as_already_revoked(monkeypatch):
    from plane.ext.capacity import google

    credential = MagicMock(encrypted_refresh_token="encrypted", encryption_key_id="key")
    client = google.GoogleCalendarClient(client_id="client", client_secret="secret")
    monkeypatch.setattr(google, "decrypt_value", lambda *_args: "refresh-token")
    monkeypatch.setattr(
        google,
        "_request",
        MagicMock(side_effect=google.requests.HTTPError("HTTP 400")),
    )

    client.revoke(credential)
