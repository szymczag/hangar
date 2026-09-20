# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

from plane.ext.capacity.training_workload import (
    clipped_minutes,
    empty_counts,
    external_counts,
    occurrence_tuples,
)

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)


def at(day, hour=9):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def test_an_occurrence_wholly_inside_the_period_counts_in_full():
    assert clipped_minutes(at(10), at(10, 13), START, END) == 240


def test_an_occurrence_straddling_the_boundary_counts_only_the_part_inside():
    """A week and the month containing it must not bill the same hour twice."""
    assert clipped_minutes(END - timedelta(hours=3), END + timedelta(hours=3), START, END) == 180
    assert clipped_minutes(START - timedelta(hours=2), START + timedelta(hours=1), START, END) == 60


def test_an_occurrence_outside_the_period_counts_nothing():
    assert clipped_minutes(END + timedelta(days=1), END + timedelta(days=1, hours=4), START, END) == 0
    # Touching the edge is not overlapping it.
    assert clipped_minutes(END, END + timedelta(hours=4), START, END) == 0


def test_confirmed_and_pending_are_counted_apart():
    counts = external_counts(
        [
            ("a", at(5), at(5, 13), "confirmed"),
            ("b", at(6), at(6, 11), "pending"),
            ("c", at(7), at(7, 10), "confirmed"),
        ],
        linked={},
        start=START,
        end=END,
    )

    assert counts == {
        "confirmed_sessions": 2,
        "confirmed_minutes": 240 + 60,
        "pending_sessions": 1,
        "pending_minutes": 120,
    }


def test_a_linked_invitation_adds_no_external_minutes():
    """It still blocks the trainer's time; those minutes are Hangar delivery."""
    occurrences = [("a", at(5), at(5, 13), "confirmed"), ("b", at(6), at(6, 11), "pending")]

    counts = external_counts(occurrences, linked={"a": "session-id"}, start=START, end=END)

    assert counts["confirmed_sessions"] == 0
    assert counts["confirmed_minutes"] == 0
    assert counts["pending_sessions"] == 1


def test_an_unknown_status_is_ignored_rather_than_crashing_the_total():
    counts = external_counts([("a", at(5), at(5, 13), "tentative")], linked={}, start=START, end=END)

    assert counts == empty_counts()


def test_the_live_path_s_serialized_events_normalize_into_counting_tuples():
    events = [{"key": "a", "start": at(5).isoformat(), "end": at(5, 13).isoformat(), "status": "confirmed"}]

    assert list(occurrence_tuples(events)) == [("a", at(5), at(5, 13), "confirmed")]
