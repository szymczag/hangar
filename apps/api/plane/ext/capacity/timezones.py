# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


def trainer_timezone(trainer):
    """Keep the last known Google zone until the calendar is disconnected."""
    try:
        calendar_zone = trainer.calendar_selection.credential.primary_calendar_timezone
        if calendar_zone:
            return calendar_zone, "google_calendar"
    except (ObjectDoesNotExist, AttributeError):
        pass
    return getattr(getattr(trainer, "user", None), "user_timezone", None) or "UTC", "profile"


def remember_primary_timezone(credential, calendars):
    primary = next((item for item in calendars if item.get("primary")), None)
    zone = primary.get("timezone") if primary else None
    if not isinstance(zone, str) or not zone:
        return
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError):
        return
    credential.primary_calendar_timezone = zone
    credential.timezone_checked_at = timezone.now()
    credential.save(update_fields=["primary_calendar_timezone", "timezone_checked_at", "updated_at"])
