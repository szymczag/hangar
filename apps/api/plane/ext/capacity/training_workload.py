# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""How recognized training invitations turn into external workload.

One rule, two readers. The weekly ledger counts invitations it has just read from
Google; the report counts the same invitations out of the database, over a range
Google would never answer in one request. They must agree, because a coordinator
comparing a week in the ledger against the month that contains it will notice
immediately if they do not -- and the rule they have to agree on is subtle: an
invitation linked to a Workshop session still blocks the trainer's time, but its
minutes are already counted as Hangar delivery, so counting them again here would
bill the same hour twice.

Keeping that in one place is the point of this module. Callers normalize their own
rows into `(key, starts_at, ends_at, status)` tuples and share everything after.
"""

from datetime import datetime

from plane.ext.models import GoogleTrainingEventLink

# The only statuses that carry external workload. `recognized_event` produces no
# others -- declined and cancelled invitations never become occurrences at all --
# but counting defensively means a future status cannot silently inflate a total.
EXTERNAL_STATUSES = ("confirmed", "pending")


def empty_counts():
    return {f"{status}_{unit}": 0 for status in EXTERNAL_STATUSES for unit in ("sessions", "minutes")}


def clipped_minutes(starts_at, ends_at, start, end):
    """Minutes of an occurrence that fall inside the requested period.

    An invitation straddling the boundary contributes only the part inside it, so
    a week and the month containing it never double-count the same hour.
    """
    overlap_start = max(start, starts_at)
    overlap_end = min(end, ends_at)
    if overlap_end <= overlap_start:
        return 0
    return int((overlap_end - overlap_start).total_seconds() // 60)


def linked_sessions(workspace_id, trainer_id, event_keys, start, end):
    """Which of these invitations are already accounted for as Hangar delivery.

    The link only counts while it still describes reality: the session has to
    overlap the period and still name this trainer. A session moved away from the
    invitation, or reassigned, makes the invitation external again -- which is the
    existing behaviour of the live path and stays true here.
    """
    if not event_keys:
        return {}
    return dict(
        GoogleTrainingEventLink.objects.filter(
            workspace_id=workspace_id,
            trainer_id=trainer_id,
            session__trainers=trainer_id,
            session__starts_at__lt=end,
            session__ends_at__gt=start,
            event_key__in=list(event_keys),
        ).values_list("event_key", "session_id")
    )


def external_counts(occurrences, *, linked, start, end):
    """Sum the invitations that are not already counted as Hangar delivery.

    `occurrences` is an iterable of `(key, starts_at, ends_at, status)`; `linked`
    is the mapping from `linked_sessions`.
    """
    counts = empty_counts()
    for key, starts_at, ends_at, status in occurrences:
        if key in linked or status not in EXTERNAL_STATUSES:
            continue
        counts[f"{status}_sessions"] += 1
        counts[f"{status}_minutes"] += clipped_minutes(starts_at, ends_at, start, end)
    return counts


def occurrence_tuples(events):
    """Normalize the live path's serialized events into counting tuples."""
    for event in events:
        yield (
            event["key"],
            datetime.fromisoformat(event["start"]),
            datetime.fromisoformat(event["end"]),
            event["status"],
        )
