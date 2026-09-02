# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework.exceptions import ValidationError

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _parse_time(value):
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Schedule times must use HH:MM format") from exc


def validate_intervals(intervals):
    if not isinstance(intervals, list) or len(intervals) > 8:
        raise ValidationError("A day must contain at most eight intervals")
    normalized = []
    for interval in intervals:
        if not isinstance(interval, dict) or set(interval) != {"start", "end"}:
            raise ValidationError("Each interval requires only start and end")
        start, end = _parse_time(interval["start"]), _parse_time(interval["end"])
        if start >= end:
            raise ValidationError("A schedule interval must end after it starts")
        normalized.append((start, end))
    normalized.sort()
    if any(current[0] < previous[1] for previous, current in zip(normalized, normalized[1:])):
        raise ValidationError("Schedule intervals may not overlap")
    return [{"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")} for start, end in normalized]


def validate_weekly_schedule(value):
    if not isinstance(value, dict) or set(value) != set(DAYS):
        raise ValidationError(f"Weekly schedule must contain exactly: {', '.join(DAYS)}")
    return {day: validate_intervals(value[day]) for day in DAYS}


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (TypeError, ZoneInfoNotFoundError) as exc:
        raise ValidationError("Unknown IANA time zone") from exc
    return value
