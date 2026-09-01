from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import ValidationError

from plane.ext.capacity.calculation import _intersections, _merge, _minutes, _subtract
from plane.ext.capacity.crypto import decrypt_value, encrypt_value
from plane.ext.capacity.schedules import validate_intervals, validate_weekly_schedule


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
