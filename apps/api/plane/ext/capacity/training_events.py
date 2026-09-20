# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from plane.ext.capacity.cache import register_busy_cache_key
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.capacity.google import GoogleCalendarError
from plane.ext.capacity.training_workload import external_counts, linked_sessions, occurrence_tuples
from plane.ext.models import GoogleTrainingRule

logger = logging.getLogger(__name__)

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


DECLINED = "declined"
ACCEPTED = "accepted"

# What a trainer's own answer means for capacity. Anything that is not an
# outright refusal blocks time, because a training somebody has not answered yet
# is still a training somebody is expected at.
_CONFIRMED_RESPONSES = frozenset({ACCEPTED})


def training_index(events, *, calendar_id):
    """What the rule's calendar says exists, keyed by occurrence identity.

    Returns `(index, cancelled_keys)`. The index is every live event on the
    calendar; the cancelled set is every event Google says is gone, which a
    caller retires rather than records.

    This half of recognition deliberately asks no question about *who*. A
    calendar whose owner hides the guest list -- the ordinary setting for a
    shared organizational calendar -- returns no attendees at all, so an
    identity test applied here would reject almost every real training. Identity
    comes from `own_responses`, read from the trainer's own copy.
    """
    index, cancelled = {}, set()
    for event in events:
        try:
            key = event_key(event, calendar_id=calendar_id)
        except GoogleCalendarError:
            # Too malformed to identify. It cannot be recorded and it cannot
            # cancel anything; a full rescan retires it by absence.
            continue
        if event.get("status") == "cancelled":
            cancelled.add(key)
            continue
        try:
            start = event_time(event.get("start"), event.get("calendar_timezone", "UTC"))
            end = event_time(event.get("end"), event.get("calendar_timezone", "UTC"))
        except GoogleCalendarError:
            continue
        if start >= end:
            continue
        index[key] = {
            "key": key,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "summary": event.get("summary"),
        }
    return index, cancelled


def own_responses(events, *, participant):
    """How this trainer answered, from their own copy of each invitation.

    An event in somebody's own calendar that also exists on the rule's calendar
    is, by construction, an invitation they received: a copy does not appear
    there otherwise. The attendee entry is read only for the answer.

    `participant` is the address Google itself verified for this credential, not
    anything a user typed. Where the answer cannot be read -- a guest list the
    API omits even to its own attendee -- the event still counts, as pending.
    Silence is not a refusal.
    """
    responses = {}
    for event in events:
        if event.get("status") == "cancelled":
            continue
        try:
            key = event_key(event, calendar_id="primary")
        except GoogleCalendarError:
            continue
        attendees = event.get("attendees")
        if not isinstance(attendees, list):
            responses[key] = "" if event.get("attendeesOmitted") else None
            continue
        mine = next(
            (
                item
                for item in attendees
                if isinstance(item, dict) and str(item.get("email", "")).casefold() == participant.casefold()
            ),
            None,
        )
        responses[key] = str(mine.get("responseStatus") or "") if mine else None
    return responses


def recognized_occurrences(index, responses):
    """The intersection: trainings on the rule's calendar that are this person's.

    Neither source alone is enough, and that is the point. The calendar knows
    what a training is; only the trainer's own copy knows whose it is. Matching
    on the occurrence key means the two halves are talking about the same
    instance of the same recurrence, not merely the same series.
    """
    occurrences = []
    for key, answer in responses.items():
        entry = index.get(key)
        if entry is None or answer is None:
            continue
        if answer.casefold() == DECLINED:
            continue
        occurrences.append(
            {
                "key": key,
                "start": entry["start"],
                "end": entry["end"],
                "status": "confirmed" if answer.casefold() in _CONFIRMED_RESPONSES else "pending",
            }
        )
    return sorted(occurrences, key=lambda item: (item["start"], item["key"]))


def event_key(event, *, calendar_id):
    """The stable identity of one occurrence, independent of who was invited.

    iCalUID plus the original occurrence distinguishes recurrence while
    deduplicating the same invitation seen through several configured calendars.

    This is also what makes the two halves of recognition comparable. The same
    occurrence read from the rule's calendar and from a trainer's own calendar
    produces the same key, because the key is derived from the event's own
    identity rather than from where it was read. Two implementations that
    drifted would silently break every link between an invitation and its
    session, so there is exactly one.
    """
    occurrence = event.get("originalStartTime") or event.get("start")
    origin = event_time(occurrence, event.get("calendar_timezone", "UTC")).astimezone(timezone.utc).isoformat()
    if not event.get("iCalUID") and not event.get("id"):
        raise GoogleCalendarError("invalid_event_identity")
    identity = event.get("iCalUID") or f"{calendar_id}:{event.get('id', '')}"
    return hmac.new(settings.SECRET_KEY.encode(), f"{identity}:{origin}".encode(), hashlib.sha256).hexdigest()


def _rule_index(client, credential, rules, start, end, *, force=False):
    """The workspace's trainings for this window, shared by every trainer.

    Cached per workspace rather than per trainer on purpose. A rule names one
    shared calendar and every trainer would read exactly the same list from it,
    so a per-trainer read multiplies a fixed answer by the size of the roster
    and spends Google's quota to learn nothing new.

    The cached value carries titles, so it is keyed on the rules and the window
    only -- never on a viewer -- and whether a given viewer may *see* a title is
    decided later, where the viewer is known.
    """
    revision = hashlib.sha256(str([(rule.id, rule.updated_at) for rule in rules]).encode()).hexdigest()[:20]
    cache_key = f"gcal:training-index:{rules[0].workspace_id}:{revision}:{start.isoformat()}:{end.isoformat()}"
    cached = cache.get(cache_key)
    if not force and isinstance(cached, dict):
        return cached
    index = {}
    for rule in rules:
        calendar_id = decrypt_value(rule.encrypted_calendar_id, rule.encryption_key_id)
        events = client.list_training_events(
            credential, calendar_id, time_min=start.isoformat(), time_max=end.isoformat()
        )
        entries, _ = training_index(events, calendar_id=calendar_id)
        index.update(entries)
    cache.set(cache_key, index, 300)
    return index


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
        index = _rule_index(client, credential, rules, start, end, force=force)
        responses = own_responses(
            client.list_own_training_responses(credential, time_min=start.isoformat(), time_max=end.isoformat()),
            participant=participant,
        )
        rows = [
            occurrence
            for occurrence in recognized_occurrences(index, responses)
            if datetime.fromisoformat(occurrence["start"]) < end and datetime.fromisoformat(occurrence["end"]) > start
        ]
        cache.set(key, rows, 300)
        cache.set(key + ":stale", rows, 3600)
        register_busy_cache_key(selection.id, key)
        register_busy_cache_key(selection.id, key + ":stale")
        return rows, "fresh"
    except (GoogleCalendarError, ValueError, KeyError):
        stale = cache.get(key + ":stale")
        return (stale, "stale") if isinstance(stale, list) else ([], "unavailable")
    except Exception as exc:  # noqa: BLE001 - only the type is logged
        # Same reasoning as the availability read: unverified blocks a booking,
        # a traceback takes the whole ledger down. `booking_preflight` accepts
        # only "fresh" or "not_configured", so this refuses rather than permits.
        logger.error("Training recognition failed with %s", type(exc).__name__)
        return [], "unavailable"


def training_workload(trainer, events, start, end):
    """The live path's view of external training, over one freshly read window.

    The counting itself lives in `plane.ext.capacity.training_workload` because
    the report answers the same question over the materialized table, and the two
    have to agree on what a linked invitation costs.
    """
    linked = linked_sessions(trainer.workspace_id, trainer.user_id, [item["key"] for item in events], start, end)
    rows = [{**event, "linked": event["key"] in linked} for event in events]
    counts = external_counts(occurrence_tuples(events), linked=linked, start=start, end=end)
    return {**counts, "events": rows}
