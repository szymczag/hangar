# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reading one rule's calendar and writing what it recognizes to the table.

The sweep is keyed on the rule, not the trainer. A rule names a *shared*
calendar, so every consenting trainer would read an identical event list from
it: sweeping per trainer would multiply Google's quota by the roster for no
extra information, and a nine-month window per trainer walks straight into the
two-thousand-event ceiling `list_training_events` enforces.

One read, then fanned out in memory: each event is offered to every consenting
trainer's own verified address through the existing `recognized_event`. The
consent boundary is preserved, because materializing anything for a trainer
still requires that trainer's own flags -- only the transport is shared.

The decisions about windows, slicing and what a pass may conclude live in
`training_sweep`; this module is the part that talks to Google and the database.
"""

import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone as django_timezone

from plane.ext.capacity.crypto import decrypt_value, encrypt_value
from plane.ext.capacity.google import GoogleCalendarError
from plane.ext.capacity.training_events import EVENTS_SCOPE, event_key, recognized_event
from plane.ext.capacity.training_sweep import (
    backoff_until,
    month_slices,
    occurrence_in_window,
    summary_for,
    sweep_window,
    wants_full_scan,
)
from plane.ext.models import (
    GoogleCalendarCredential,
    TrainerProfile,
    TrainerTrainingSyncState,
    TrainingCalendarSyncState,
    TrainingEventOccurrence,
)

logger = logging.getLogger(__name__)


def consenting_trainers(workspace_id):
    """Trainers whose own flags permit reading training invitations for them.

    Returns `(profile, participant_email)` pairs. A trainer missing any of the
    flags is not an error -- they simply have no occurrences, and the report
    says so rather than rendering them as somebody who ran no training.
    """
    profiles = (
        TrainerProfile.objects.filter(workspace_id=workspace_id, status=TrainerProfile.Status.ACTIVE)
        .select_related("calendar_selection__credential")
        .order_by("id")
    )
    readers = []
    for profile in profiles:
        selection = getattr(profile, "calendar_selection", None)
        if selection is None:
            _remember_consent(profile, TrainerTrainingSyncState.ConsentState.NOT_CONNECTED)
            continue
        credential = selection.credential
        if credential.status != GoogleCalendarCredential.Status.CONNECTED:
            _remember_consent(profile, TrainerTrainingSyncState.ConsentState.REAUTH_REQUIRED)
            continue
        if (
            not selection.training_events_enabled
            or EVENTS_SCOPE not in credential.granted_scopes
            or not credential.encrypted_google_email
        ):
            _remember_consent(profile, TrainerTrainingSyncState.ConsentState.CONSENT_MISSING)
            continue
        email = decrypt_value(credential.encrypted_google_email, credential.encryption_key_id)
        readers.append((profile, email))
    return readers


def _remember_consent(profile, state, *, error_code=""):
    TrainerTrainingSyncState.objects.update_or_create(
        trainer_profile=profile,
        defaults={"consent_state": state, "last_error_code": error_code},
    )


def sync_state_for(rule, now):
    """The bookkeeping row for this rule, created on first sight."""
    start, end = sweep_window(now)
    state, _ = TrainingCalendarSyncState.objects.get_or_create(
        rule=rule,
        defaults={
            "workspace_id": rule.workspace_id,
            "window_starts_at": start,
            "window_ends_at": end,
        },
    )
    return state


def _reader(readers, offset):
    """Whose credential performs the read.

    Rotating by the failure count means a calendar that just failed through one
    person's connection is retried through somebody else's, which is what
    distinguishes "this calendar is gone" from "this one account lost access".
    """
    return readers[offset % len(readers)]


def _upsert(occurrence, *, profile, rule, calendar_hash, summary, now):
    encrypted, key_id = encrypt_value(summary) if summary else ("", "")
    TrainingEventOccurrence.objects.update_or_create(
        workspace_id=profile.workspace_id,
        trainer_id=profile.user_id,
        event_key=occurrence["key"],
        defaults={
            "trainer_profile": profile,
            "rule": rule,
            "rule_label": rule.label,
            "calendar_id_hash": calendar_hash,
            "starts_at": datetime.fromisoformat(occurrence["start"]),
            "ends_at": datetime.fromisoformat(occurrence["end"]),
            "status": occurrence["status"],
            "state": TrainingEventOccurrence.State.ACTIVE,
            "encrypted_summary": encrypted,
            "encryption_key_id": key_id,
            "last_seen_at": now,
        },
        create_defaults={
            "trainer_profile": profile,
            "rule": rule,
            "rule_label": rule.label,
            "calendar_id_hash": calendar_hash,
            "starts_at": datetime.fromisoformat(occurrence["start"]),
            "ends_at": datetime.fromisoformat(occurrence["end"]),
            "status": occurrence["status"],
            "state": TrainingEventOccurrence.State.ACTIVE,
            "encrypted_summary": encrypted,
            "encryption_key_id": key_id,
            "first_seen_at": now,
            "last_seen_at": now,
        },
    )


def _cancel(rule, cancelled_keys, now):
    """Retire occurrences whose invitation Google says is gone.

    Worth doing in the incremental pass even though the daily full scan would
    also catch it: a cancelled training that goes on blocking a trainer and
    inflating a report until tomorrow is the kind of wrongness somebody plans
    staffing around.
    """
    if not cancelled_keys:
        return 0
    return TrainingEventOccurrence.objects.filter(rule=rule, event_key__in=list(cancelled_keys)).exclude(
        state=TrainingEventOccurrence.State.CANCELLED
    ).update(state=TrainingEventOccurrence.State.CANCELLED, last_seen_at=now, updated_at=now)


def sweep_rule(client, rule, *, now=None, full=False):
    """Read one rule's calendar and write what it recognizes.

    Returns a summary dict; raises nothing for an ordinary Google failure, which
    is recorded on the state row so the dispatcher can back off.
    """
    now = now or django_timezone.now()
    state = sync_state_for(rule, now)
    readers = consenting_trainers(rule.workspace_id)
    if not readers:
        # Nobody has consented, so there is nothing this rule may read. Not a
        # failure: the report explains it per trainer.
        state.last_success_at = now
        state.last_error_code = ""
        state.failure_count = 0
        state.save(update_fields=["last_success_at", "last_error_code", "failure_count", "updated_at"])
        return {"matched": 0, "cancelled": 0, "disappeared": 0, "readers": 0}

    window_start, window_end = sweep_window(now)
    full = full or wants_full_scan(state.last_full_scan_at, now)
    updated_min = None if full else _incremental_floor(state)
    profile, _ = _reader(readers, state.failure_count)
    credential = profile.calendar_selection.credential

    calendar_id = decrypt_value(rule.encrypted_calendar_id, rule.encryption_key_id)
    organizer = decrypt_value(rule.encrypted_organizer, rule.encryption_key_id)
    calendar_hash = _calendar_hash(calendar_id)

    matched = 0
    cancelled_keys = set()
    try:
        for slice_start, slice_end in month_slices(window_start, window_end):
            events = client.list_training_events(
                credential,
                calendar_id,
                time_min=slice_start.isoformat().replace("+00:00", "Z"),
                time_max=slice_end.isoformat().replace("+00:00", "Z"),
                updated_min=updated_min.isoformat().replace("+00:00", "Z") if updated_min else None,
            )
            for event in events:
                if event.get("status") == "cancelled":
                    try:
                        cancelled_keys.add(event_key(event, calendar_id=calendar_id))
                    except GoogleCalendarError:
                        # An event too malformed to identify cannot cancel
                        # anything; the full scan will retire it by absence.
                        continue
                    continue
                for reader_profile, email in readers:
                    occurrence = recognized_event(
                        event, organizer=organizer, participant=email, calendar_id=calendar_id
                    )
                    if occurrence is None:
                        continue
                    if not occurrence_in_window(
                        datetime.fromisoformat(occurrence["start"]),
                        datetime.fromisoformat(occurrence["end"]),
                        window_start,
                        window_end,
                    ):
                        continue
                    _upsert(
                        occurrence,
                        profile=reader_profile,
                        rule=rule,
                        calendar_hash=calendar_hash,
                        summary=summary_for(event, matched=True),
                        now=now,
                    )
                    matched += 1
    except (GoogleCalendarError, ValueError, KeyError) as exc:
        code = getattr(exc, "code", "provider_unavailable")
        state.failure_count += 1
        state.last_error_code = code
        state.available_at = backoff_until(now, state.failure_count)
        state.save(update_fields=["failure_count", "last_error_code", "available_at", "updated_at"])
        logger.warning("Training calendar sweep failed", extra={"error_code": code, "rule_id": str(rule.id)})
        return {"matched": 0, "cancelled": 0, "disappeared": 0, "error": code}

    with transaction.atomic():
        cancelled = _cancel(rule, cancelled_keys, now)
        disappeared = _mark_disappeared(rule, now, window_start, window_end) if full else 0
        state.window_starts_at = window_start
        state.window_ends_at = window_end
        state.last_success_at = now
        state.last_incremental_at = now
        state.last_error_code = ""
        state.failure_count = 0
        state.available_at = now
        if full:
            state.last_full_scan_at = now
        state.save()
        for reader_profile, _ in readers:
            _remember_consent(reader_profile, TrainerTrainingSyncState.ConsentState.OK)
            TrainerTrainingSyncState.objects.filter(trainer_profile=reader_profile).update(
                last_materialized_at=now
            )

    return {"matched": matched, "cancelled": cancelled, "disappeared": disappeared, "readers": len(readers)}


def _incremental_floor(state):
    from plane.ext.capacity.training_sweep import incremental_floor

    return incremental_floor(state.last_success_at)


def _calendar_hash(calendar_id):
    from plane.ext.models import TrainerCalendarSelection

    return TrainerCalendarSelection.calendar_hash(calendar_id)


def _mark_disappeared(rule, pass_started_at, window_start, window_end):
    """Only ever called for a full pass -- see `training_sweep.disappeared_after`."""
    return (
        TrainingEventOccurrence.objects.filter(
            rule=rule,
            starts_at__lt=window_end,
            ends_at__gt=window_start,
            last_seen_at__lt=pass_started_at,
            state=TrainingEventOccurrence.State.ACTIVE,
        ).update(state=TrainingEventOccurrence.State.DISAPPEARED, updated_at=django_timezone.now())
    )
