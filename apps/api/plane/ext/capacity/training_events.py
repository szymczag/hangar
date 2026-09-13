# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from plane.ext.capacity.cache import register_busy_cache_key
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.capacity.google import GoogleCalendarError
from plane.ext.models import GoogleTrainingRule, GoogleTrainingEventLink

EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"


def rules_revision(workspace_id):
    return tuple(
        GoogleTrainingRule.objects.filter(workspace_id=workspace_id).order_by("id").values_list("id", "updated_at")
    )


def event_time(value, zone):
    if not isinstance(value, dict):
        raise GoogleCalendarError("invalid_event_time")
    if value.get("dateTime"):
        result = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise GoogleCalendarError("invalid_event_time")
        return result
    if value.get("date"):
        return datetime.fromisoformat(value["date"]).replace(tzinfo=ZoneInfo(zone))
    raise GoogleCalendarError("invalid_event_time")


def recognized_event(event, *, organizer, participant, calendar_id):
    """Only exact organizer + verified OAuth email; creator and self are not identity."""
    organizer_data = event.get("organizer") or {}
    attendees = event.get("attendees") or []
    if (
        not isinstance(organizer_data, dict)
        or not isinstance(attendees, list)
        or any(not isinstance(item, dict) for item in attendees)
    ):
        raise GoogleCalendarError("invalid_event_participants")
    if event.get("status") == "cancelled" or str(organizer_data.get("email", "")).casefold() != organizer.casefold():
        return None
    if event.get("attendeesOmitted"):
        raise GoogleCalendarError("incomplete_event_participants")
    attendee = next(
        (item for item in attendees if str(item.get("email", "")).casefold() == participant.casefold()),
        None,
    )
    if attendee is None or attendee.get("responseStatus") == "declined":
        return None
    status = "confirmed" if attendee.get("responseStatus") == "accepted" else "pending"
    start = event_time(event.get("start"), event.get("calendar_timezone", "UTC"))
    end = event_time(event.get("end"), event.get("calendar_timezone", "UTC"))
    if start >= end:
        raise GoogleCalendarError("invalid_event_time")
    # iCalUID plus original occurrence distinguishes recurrence while deduplicating
    # the same invitation seen through multiple configured calendars.
    occurrence = event.get("originalStartTime") or event.get("start")
    origin = event_time(occurrence, event.get("calendar_timezone", "UTC")).astimezone(timezone.utc).isoformat()
    if not event.get("iCalUID") and not event.get("id"):
        raise GoogleCalendarError("invalid_event_identity")
    identity = event.get("iCalUID") or f"{calendar_id}:{event.get('id', '')}"
    key = hmac.new(settings.SECRET_KEY.encode(), f"{identity}:{origin}".encode(), hashlib.sha256).hexdigest()
    return {"key": key, "start": start.isoformat(), "end": end.isoformat(), "status": status}


def training_events(trainer, start, end, *, force=False):
    rules = list(GoogleTrainingRule.objects.filter(workspace_id=trainer.workspace_id).order_by("id"))
    if not rules:
        return [], "not_configured"
    try:
        selection = trainer.calendar_selection
    except ObjectDoesNotExist:
        return [], "consent_required"
    credential = selection.credential
    if (
        not selection.training_events_enabled
        or EVENTS_SCOPE not in credential.granted_scopes
        or not credential.encrypted_google_email
    ):
        return [], "consent_required"
    revision = hashlib.sha256(str([(rule.id, rule.updated_at) for rule in rules]).encode()).hexdigest()[:20]
    key = f"gcal:training:{selection.id}:{selection.revision}:{revision}:{start.isoformat()}:{end.isoformat()}"
    cached = cache.get(key)
    if not force and isinstance(cached, list):
        return cached, "fresh"
    try:
        from plane.ext.capacity.calculation import _google_client

        client = _google_client()
        participant = decrypt_value(credential.encrypted_google_email, credential.encryption_key_id)
        results = {}
        calendars = {}
        for rule in rules:
            calendar_id = decrypt_value(rule.encrypted_calendar_id, rule.encryption_key_id)
            organizer = decrypt_value(rule.encrypted_organizer, rule.encryption_key_id)
            if calendar_id not in calendars:
                calendars[calendar_id] = client.list_events(
                    credential, calendar_id, time_min=start.isoformat(), time_max=end.isoformat()
                )
            for event in calendars[calendar_id]:
                occurrence = recognized_event(
                    event, organizer=organizer, participant=participant, calendar_id=calendar_id
                )
                if (
                    occurrence
                    and datetime.fromisoformat(occurrence["start"]) < end
                    and datetime.fromisoformat(occurrence["end"]) > start
                ):
                    results[occurrence["key"]] = occurrence
        rows = sorted(results.values(), key=lambda item: (item["start"], item["key"]))
        cache.set(key, rows, 300)
        cache.set(key + ":stale", rows, 3600)
        register_busy_cache_key(selection.id, key)
        register_busy_cache_key(selection.id, key + ":stale")
        return rows, "fresh"
    except (GoogleCalendarError, ValueError, KeyError):
        stale = cache.get(key + ":stale")
        return (stale, "stale") if isinstance(stale, list) else ([], "unavailable")


def training_workload(trainer, events, start, end):
    linked = dict(
        GoogleTrainingEventLink.objects.filter(
            workspace_id=trainer.workspace_id,
            trainer_id=trainer.user_id,
            session__trainers=trainer.user_id,
            session__starts_at__lt=end,
            session__ends_at__gt=start,
            event_key__in=[item["key"] for item in events],
        ).values_list("event_key", "session_id")
    )
    counts = {"confirmed_sessions": 0, "confirmed_minutes": 0, "pending_sessions": 0, "pending_minutes": 0}
    rows = []
    for event in events:
        session_id = linked.get(event["key"])
        rows.append({**event, "linked": bool(session_id)})
        if session_id:
            continue
        prefix = event["status"]
        counts[f"{prefix}_sessions"] += 1
        counts[f"{prefix}_minutes"] += max(
            0,
            int(
                (
                    min(end, datetime.fromisoformat(event["end"])) - max(start, datetime.fromisoformat(event["start"]))
                ).total_seconds()
                // 60
            ),
        )
    return {**counts, "events": rows}
