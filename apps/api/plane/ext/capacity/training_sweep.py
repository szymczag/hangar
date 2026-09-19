# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Deciding what a sweep of a training calendar should read and conclude.

Everything here is a pure decision about windows, slices and what a pass is
entitled to conclude. The Google call and the database write live in the task
that uses these, so the awkward parts -- which are all about time -- can be
tested without either.

Two asymmetries drive the whole design.

The first is that a bounded window and an incremental read pull in opposite
directions. Google will not combine a sync token with a time range, so an
incremental pass has to be `updatedMin` over the same window. That catches
anything created or edited, but it cannot catch an event that was *moved out* of
the window: its new time fails the filter, so the pass simply never sees it. An
incremental pass therefore may never conclude that anything disappeared. Only a
full rescan, which sees the whole window, may do that.

The second is that the past and the future are not equally interesting. The
future is planning and moves constantly; the past is the reporting product and
must not be thrown away just because it fell out of the sweep window.
"""

from calendar import monthrange
from datetime import datetime, timedelta, timezone

# How far the sweep looks. The past bound is how far back a sweep will re-read,
# not how much history is kept -- occurrences outside it are left alone, because
# a report about last year is exactly what this table exists to answer.
DEFAULT_PAST_DAYS = 90
DEFAULT_FUTURE_DAYS = 180

# An incremental pass re-reads a little before its last success, so an event
# updated while the previous pass was mid-flight is not missed in the gap.
INCREMENTAL_OVERLAP = timedelta(minutes=10)

# A full rescan is what lets the sweep conclude that something disappeared, and
# it costs a whole window of reads, so it runs daily rather than every pass.
FULL_SCAN_INTERVAL = timedelta(hours=24)


def month_start(moment):
    return moment.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(moment):
    days = monthrange(moment.year, moment.month)[1]
    return month_start(moment) + timedelta(days=days)


def sweep_window(now, *, past_days=DEFAULT_PAST_DAYS, future_days=DEFAULT_FUTURE_DAYS):
    """The range a sweep covers, snapped outwards to whole months.

    Snapping keeps the boundary still for most of a month, so the slices a pass
    reads -- and therefore its cache keys and its idea of which occurrences are
    in scope -- do not shift underneath it every single day.
    """
    start = month_start(now - timedelta(days=past_days))
    end = month_start(now + timedelta(days=future_days))
    return start, next_month(end)


def month_slices(start, end):
    """Whole-month chunks of the window.

    `list_events` refuses a window holding more than two thousand events, and a
    shared training calendar over nine months can reach that. A month is small
    enough to stay under it and large enough not to multiply round trips.
    """
    slices = []
    cursor = month_start(start)
    while cursor < end:
        following = next_month(cursor)
        slices.append((max(cursor, start), min(following, end)))
        cursor = following
    return slices


def wants_full_scan(state_last_full_scan_at, now, *, interval=FULL_SCAN_INTERVAL):
    """A calendar never fully scanned is due for one immediately."""
    if state_last_full_scan_at is None:
        return True
    return now - state_last_full_scan_at >= interval


def incremental_floor(last_success_at, *, overlap=INCREMENTAL_OVERLAP):
    """`updatedMin` for an incremental pass, or `None` when a full read is owed."""
    if last_success_at is None:
        return None
    return last_success_at - overlap


def backoff_until(now, failure_count, *, base=timedelta(seconds=30), ceiling=timedelta(hours=6)):
    """When a failing calendar may be tried again.

    Doubling, capped. The cap matters more than the curve: a calendar that has
    been failing all morning should still be retried this afternoon, because the
    usual cause is a permission somebody is in the middle of fixing.
    """
    if failure_count <= 0:
        return now
    delay = base * (2 ** min(failure_count - 1, 16))
    return now + min(delay, ceiling)


def disappeared_after(pass_started_at, *, full):
    """The `last_seen_at` cutoff below which rows count as gone.

    `None` from an incremental pass, and that is the whole point: it only ever
    saw the events Google said had changed, so everything it did not see is
    simply everything that did not change. Concluding disappearance from that
    would delete most of the calendar on every run.
    """
    return pass_started_at if full else None


def occurrence_in_window(starts_at, ends_at, start, end):
    """Whether an occurrence belongs to this window at all.

    Touching the boundary is not overlapping it, matching how the rest of the
    capacity code treats ranges.
    """
    return starts_at < end and ends_at > start


def summary_for(event, *, matched):
    """The title to store, and only for an event that matched a rule.

    The filter is the security boundary of the whole titles feature, so it is a
    named function rather than an inline condition: an event that did not match
    must never hand its title to anything that could persist or log it. Callers
    pass `matched` from `recognized_event`, which has already applied the
    organizer and participant checks.
    """
    if not matched:
        return ""
    title = event.get("summary")
    if not isinstance(title, str):
        return ""
    return title.strip()[:200]


def utc(value):
    """Coerce a datetime to aware UTC, rejecting naive input outright."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("a timezone-aware datetime is required")
    return value.astimezone(timezone.utc)
