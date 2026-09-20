# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Writing scheduled workshops into the shared training calendar.

The direction opposite to recognition, and built on the same two-calendar shape:
Hangar creates the event on the rule's calendar and invites the trainer, whose
own copy then closes the loop through the intersection in `training_events`.
Nothing here depends on who Google names as organizer, which is what makes it
possible at all -- an event created on a shared calendar is organized by the
calendar, never by the account that created it.

Three properties the rest of this module exists to hold:

**Planning never waits for Google.** The request records intent in the same
transaction as the session; a worker reconciles afterwards. A coordinator who
cannot book because a calendar API is slow would stop using the planner, and
would be right to.

**Writing twice is not possible.** The event identifier is derived from the
session and the trainer, so a redelivered message or a retry after an answer we
never saw lands on the same identifier and Google refuses the duplicate.

**A row is never lost with its session.** Sessions are hard-deleted when a
schedule is replaced, and the row that still owes Google a deletion is exactly
the row that matters then, so it survives on a durable key of its own.
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from plane.ext.capacity.crypto import decrypt_value
from plane.ext.capacity.google import GoogleCalendarError
from plane.ext.models import GoogleTrainingRule, WorkshopSessionCalendarEvent

logger = logging.getLogger(__name__)

# Google accepts event identifiers of 5-1024 characters from base32hex, which is
# the digits and the letters a-v. Not the full alphabet, so the digest is encoded
# rather than hex-formatted, and lower-cased because the alphabet is.
_ID_ALPHABET_PAD = "="


def writeback_enabled() -> bool:
    return bool(
        settings.GOOGLE_CALENDAR_CAPACITY_ENABLED and getattr(settings, "GOOGLE_CALENDAR_WRITEBACK_ENABLED", False)
    )


def event_id_for(session_id, trainer_id) -> str:
    """The identifier Google will know this invitation by.

    Derived rather than random, and keyed with the instance secret so it cannot
    be guessed from a session identifier alone. Deriving it is what makes
    `insert` idempotent: the second attempt collides with the first instead of
    creating a second event, so at-least-once delivery cannot produce two
    invitations for one session.
    """
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{session_id}:{trainer_id}".encode(),
        hashlib.sha256,
    ).digest()
    encoded = base64.b32hexencode(digest).decode().rstrip(_ID_ALPHABET_PAD).lower()
    return f"hg{encoded[:40]}"


def fingerprint(payload: dict) -> str:
    """A stable digest of what Google was asked for.

    Compared before writing so that a row whose desired state did not actually
    change costs nothing. Sorted keys, because a dictionary that serialized in a
    different order would otherwise look like a change every time.
    """
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def desired_state(*, summary, starts_at, ends_at, attendee_email) -> dict:
    """Everything about an invitation that Google would notice changing.

    Fingerprinted from here and sent from `event_payload`, both built from this
    one description, so a row cannot be judged unchanged while the payload it
    would send is different.
    """
    return {
        "summary": summary,
        "start": starts_at.isoformat(),
        "end": ends_at.isoformat(),
        "attendee": attendee_email,
    }


def trainer_credential(user):
    """The trainer's own Google connection, or `None`."""
    from plane.ext.models import TrainerCalendarSelection

    selection = TrainerCalendarSelection.objects.filter(trainer__user=user).select_related("credential").first()
    return selection.credential if selection else None


def event_summary(source_issue_id) -> str:
    """The work item's name, which is what a reader of the calendar wants."""
    from plane.db.models import Issue

    issue = Issue.objects.filter(id=source_issue_id).only("name").first() if source_issue_id else None
    return (issue.name if issue else "Workshop")[:1024]


def event_payload(*, event_id, summary, description, starts_at, ends_at, attendee_email, session_id, workspace_id):
    """What Hangar asks Google to create.

    The window is the delivery itself, not the preparation and travel around it.
    Those are Hangar's internal arithmetic for deciding whether somebody is free;
    a three-hour entry for a one-hour training surprises the people reading the
    calendar, and this calendar is read by people.

    Only the trainer is invited. Inviting clients is a separate decision about
    sending mail to people outside the organization, and it is not this one.
    """
    return {
        "id": event_id,
        "summary": summary,
        "description": description,
        "start": {"dateTime": starts_at.isoformat().replace("+00:00", "Z"), "timeZone": "UTC"},
        "end": {"dateTime": ends_at.isoformat().replace("+00:00", "Z"), "timeZone": "UTC"},
        "attendees": [{"email": attendee_email}],
        "extendedProperties": {"private": {"hangarSession": str(session_id), "hangarWorkspace": str(workspace_id)}},
        "reminders": {"useDefault": True},
        "guestsCanModify": False,
    }


def _rule_for(workspace_id):
    """The calendar a workshop is written to.

    One rule per workspace is the shape this supports today; with several, the
    first by label is used and the choice is recorded rather than guessed at
    silently. Returning `None` is an ordinary answer -- a workspace that has
    configured no training calendar simply does not get write-back.
    """
    return (
        GoogleTrainingRule.objects.filter(workspace_id=workspace_id)
        .select_related("writer_credential")
        .order_by("label", "id")
        .first()
    )


def _writer(rule):
    """The credential that may write, or `None` with the reason left to the caller."""
    if rule is None:
        return None
    credential = rule.writer_credential
    if credential is None:
        return None
    from plane.ext.models import GoogleCalendarCredential

    if credential.status != GoogleCalendarCredential.Status.CONNECTED:
        return None
    return credential


def reconcile_session(session, *, actor=None):
    """Bring the outbox in line with who is now delivering this session.

    Returns the identifiers of rows that need a worker. Trainers who were
    removed are not deleted here: their row is flipped to `absent` so the worker
    still has something to act on, because an invitation that was sent has to be
    withdrawn rather than forgotten.
    """
    if not writeback_enabled():
        return []

    rule = _rule_for(session.schedule.workspace_id)
    credential = _writer(rule)
    subject = credential.google_subject if credential else ""
    issue_id = session.schedule.issue_id
    summary = session.schedule.issue.name if session.schedule.issue_id else "Workshop"

    trainers = list(session.trainers.all())
    touched = []
    now = timezone.now()

    for trainer in trainers:
        digest = fingerprint(
            desired_state(
                summary=summary,
                starts_at=session.starts_at,
                ends_at=session.ends_at,
                attendee_email=attendee_for(trainer_credential(trainer)),
            )
        )
        row, created = WorkshopSessionCalendarEvent.objects.get_or_create(
            trainer=trainer,
            source_session_id=session.id,
            defaults={
                "workspace_id": session.schedule.workspace_id,
                "session": session,
                "source_issue_id": issue_id,
                "rule": rule,
                "requested_by": actor,
                "credential": credential,
                "credential_subject": subject,
                "google_event_id": event_id_for(session.id, trainer.id),
                "desired_starts_at": session.starts_at,
                "desired_ends_at": session.ends_at,
                "desired_fingerprint": digest,
                "state": (
                    WorkshopSessionCalendarEvent.State.PENDING
                    if credential
                    else WorkshopSessionCalendarEvent.State.BLOCKED_NO_WRITER
                ),
                "available_at": now,
            },
        )
        if not created:
            unchanged = (
                row.intent == WorkshopSessionCalendarEvent.Intent.PRESENT
                and row.desired_fingerprint == digest
                and row.credential_subject == subject
            )
            if unchanged:
                continue
            row.session = session
            row.source_issue_id = issue_id
            row.rule = rule
            row.credential = credential
            row.credential_subject = subject
            row.intent = WorkshopSessionCalendarEvent.Intent.PRESENT
            row.desired_starts_at = session.starts_at
            row.desired_ends_at = session.ends_at
            row.desired_fingerprint = digest
            row.revision += 1
            row.attempts = 0
            row.available_at = now
            row.state = (
                WorkshopSessionCalendarEvent.State.PENDING
                if credential
                else WorkshopSessionCalendarEvent.State.BLOCKED_NO_WRITER
            )
            row.save()
        touched.append(row.id)

    keeping = {trainer.id for trainer in trainers}
    for row in WorkshopSessionCalendarEvent.objects.filter(source_session_id=session.id).exclude(
        trainer_id__in=keeping
    ):
        if row.intent == WorkshopSessionCalendarEvent.Intent.ABSENT:
            continue
        touched.extend(_mark_absent(row, now))

    return touched


def mark_sessions_absent(session_ids, *, actor=None):
    """Withdraw every invitation for sessions that are going away.

    Called before the sessions are deleted, because afterwards there is nothing
    left to enumerate trainers from. The rows survive the deletion on purpose --
    they are what still owes Google a removal.
    """
    if not writeback_enabled() or not session_ids:
        return []
    now = timezone.now()
    touched = []
    for row in WorkshopSessionCalendarEvent.objects.filter(
        source_session_id__in=list(session_ids), intent=WorkshopSessionCalendarEvent.Intent.PRESENT
    ):
        if actor is not None and row.requested_by_id is None:
            row.requested_by = actor
        touched.extend(_mark_absent(row, now))
    return touched


def _mark_absent(row, now):
    row.intent = WorkshopSessionCalendarEvent.Intent.ABSENT
    row.revision += 1
    row.attempts = 0
    row.available_at = now
    # Deliberately not reset to PENDING when there is nothing to withdraw: a row
    # that never reached Google has no event to remove, so it is already done.
    row.state = (
        WorkshopSessionCalendarEvent.State.SYNCED
        if not row.google_event_id or row.synced_revision == 0
        else WorkshopSessionCalendarEvent.State.PENDING
    )
    if row.state == WorkshopSessionCalendarEvent.State.SYNCED:
        row.synced_revision = row.revision
        row.synced_at = now
    row.save()
    return [row.id] if row.state == WorkshopSessionCalendarEvent.State.PENDING else []


def enqueue(row_ids):
    """Hand the worker its work, once the transaction that created it commits.

    On commit rather than immediately: a task that starts before the session is
    visible reads a row that is not there yet, and a transaction that rolls back
    would otherwise have already asked Google to create an event for a session
    that never existed.
    """
    if not row_ids:
        return

    def _dispatch():
        from plane.ext.tasks import sync_workshop_calendar_events

        sync_workshop_calendar_events.delay([str(row_id) for row_id in row_ids])

    transaction.on_commit(_dispatch)


def attendee_for(credential):
    """The address to invite, which must be the one recognition will match.

    Taken from the trainer's own verified Google identity rather than from their
    Hangar account: the copy of the invitation only appears in the calendar of
    the address Google actually delivered it to, and a different address would
    send an invitation nothing ever recognizes.
    """
    if credential is None or not credential.encrypted_google_email:
        return ""
    return decrypt_value(credential.encrypted_google_email, credential.encryption_key_id)


def claim_rows(now, *, limit=None, lease_seconds=None):
    """Take a lease on the rows that owe Google work.

    The predicate is `synced_revision != revision`, not the state: a row whose
    desired state moved on is owed work whatever it last recorded about itself,
    which is what makes a row stuck in `failed` recoverable by simply editing
    the session again.

    `skip_locked` so that two dispatchers divide the work rather than one
    waiting on the other, and never hand the same row to two workers -- two
    writers racing on one event is how duplicate invitations would happen.
    """
    limit = limit or settings.GOOGLE_CALENDAR_WRITE_BATCH
    lease_seconds = lease_seconds or settings.GOOGLE_CALENDAR_WRITE_LEASE_SECONDS
    expires_at = now + timedelta(seconds=lease_seconds)
    claimed = []
    with transaction.atomic():
        rows = list(
            WorkshopSessionCalendarEvent.objects.select_for_update(skip_locked=True)
            .filter(available_at__lte=now)
            .filter(Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lt=now))
            .exclude(state=WorkshopSessionCalendarEvent.State.BLOCKED)
            .exclude(synced_revision=F("revision"))
            .order_by("available_at", "id")[:limit]
        )
        for row in rows:
            row.lease_token = uuid4()
            row.lease_expires_at = expires_at
            claimed.append((row.id, row.lease_token))
        if rows:
            WorkshopSessionCalendarEvent.objects.bulk_update(rows, ["lease_token", "lease_expires_at", "updated_at"])
    return claimed


def release_row(row_id, lease_token):
    """Hand the row back, but only if this worker still holds it."""
    return WorkshopSessionCalendarEvent.objects.filter(id=row_id, lease_token=lease_token).update(
        lease_token=None, lease_expires_at=None
    )


def backoff_until(now, attempts, *, base=timedelta(seconds=30), ceiling=timedelta(hours=6)):
    if attempts <= 0:
        return now
    return now + min(base * (2 ** min(attempts - 1, 16)), ceiling)


def sync_row(client, row, *, now=None):
    """Make Google agree with one outbox row.

    Returns a short summary rather than raising: an ordinary Google failure is
    this row's problem and is recorded on it, because retrying through Celery
    would multiply exactly the requests that caused a rate limit.
    """
    now = now or timezone.now()
    row.last_attempt_at = now

    credential = row.credential
    if credential is None:
        row.state = WorkshopSessionCalendarEvent.State.BLOCKED_NO_WRITER
        row.save(update_fields=["state", "last_attempt_at", "updated_at"])
        return {"result": "blocked_no_writer"}

    # The identity gate. A rule whose writing account changed between planning
    # and writing must not have this row written by whoever holds it now: the
    # person who planned it consented to one account acting, and an event
    # appearing from another is a surprise in somebody else's calendar.
    if row.credential_subject and credential.google_subject != row.credential_subject:
        row.state = WorkshopSessionCalendarEvent.State.BLOCKED
        row.last_error_code = "writer_changed"
        row.save(update_fields=["state", "last_error_code", "last_attempt_at", "updated_at"])
        return {"result": "blocked"}

    if row.rule is None:
        row.state = WorkshopSessionCalendarEvent.State.BLOCKED
        row.last_error_code = "rule_removed"
        row.save(update_fields=["state", "last_error_code", "last_attempt_at", "updated_at"])
        return {"result": "blocked"}

    calendar_id = decrypt_value(row.rule.encrypted_calendar_id, row.rule.encryption_key_id)
    target_revision = row.revision

    try:
        if row.intent == WorkshopSessionCalendarEvent.Intent.ABSENT:
            client.delete_event(credential, calendar_id, row.google_event_id)
        else:
            attendee = attendee_for(trainer_credential(row.trainer))
            if not attendee:
                # The trainer has no verified Google identity, so an invitation
                # would go to an address recognition never matches. Blocked
                # rather than failed: retrying cannot fix it, connecting can.
                row.state = WorkshopSessionCalendarEvent.State.BLOCKED
                row.last_error_code = "trainer_not_connected"
                row.save(update_fields=["state", "last_error_code", "last_attempt_at", "updated_at"])
                return {"result": "blocked"}
            payload = event_payload(
                event_id=row.google_event_id,
                summary=event_summary(row.source_issue_id),
                description="",
                starts_at=row.desired_starts_at,
                ends_at=row.desired_ends_at,
                attendee_email=attendee,
                session_id=row.source_session_id,
                workspace_id=row.workspace_id,
            )
            try:
                created = client.insert_event(credential, calendar_id, payload)
            except GoogleCalendarError as exc:
                if exc.code != "already_exists":
                    raise
                # Ours already, by construction: the identifier is derived from
                # this session and this trainer, so nothing else could have
                # created it. Updating is the reconciliation.
                created = client.update_event(credential, calendar_id, row.google_event_id, payload)
            row.google_ical_uid = str(created.get("iCalUID") or "")
    except GoogleCalendarError as exc:
        code = getattr(exc, "code", "provider_unavailable")
        if code == "reauthorization_required":
            row.state = WorkshopSessionCalendarEvent.State.BLOCKED_NO_WRITER
            row.last_error_code = code
            row.save(update_fields=["state", "last_error_code", "last_attempt_at", "updated_at"])
            return {"result": "blocked_no_writer", "error": code}
        row.attempts += 1
        row.last_error_code = code
        row.available_at = backoff_until(now, row.attempts)
        row.state = (
            WorkshopSessionCalendarEvent.State.FAILED
            if row.attempts >= 12
            else WorkshopSessionCalendarEvent.State.PENDING
        )
        row.save(
            update_fields=["attempts", "last_error_code", "available_at", "state", "last_attempt_at", "updated_at"]
        )
        return {"result": "error", "error": code}

    row.synced_revision = target_revision
    row.synced_at = now
    row.state = WorkshopSessionCalendarEvent.State.SYNCED
    row.attempts = 0
    row.last_error_code = ""
    row.save()
    return {"result": "synced"}


def reconcile_orphans(now=None):
    """Withdraw invitations whose session is gone, however it went.

    The helpers in the scheduling views cover the ordinary paths, and they are
    not the authority -- deleting the work item cascades into the schedule and
    its sessions without passing through any of them, and so does anything else
    that reaches the tables directly. This task is the authority: it compares
    every live row against what the database now says and fixes the difference.

    Cheap when there is nothing to do, which is almost always: one indexed query
    over rows that still intend to be present.
    """
    now = now or timezone.now()
    touched = []
    rows = (
        WorkshopSessionCalendarEvent.objects.filter(intent=WorkshopSessionCalendarEvent.Intent.PRESENT)
        .select_related("session")
        .only(
            "id",
            "intent",
            "revision",
            "synced_revision",
            "state",
            "attempts",
            "available_at",
            "google_event_id",
            "session",
            "source_session_id",
            "trainer_id",
            "synced_at",
        )
    )
    for row in rows.iterator(chunk_size=200):
        session = row.session
        if session is None:
            touched.extend(_mark_absent(row, now))
            continue
        if not session.trainers.filter(pk=row.trainer_id).exists():
            touched.extend(_mark_absent(row, now))
    return touched
