# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import pytest

from plane.ext.capacity.training_sweep import (
    FULL_SCAN_INTERVAL,
    backoff_until,
    disappeared_after,
    incremental_floor,
    month_slices,
    occurrence_in_window,
    summary_for,
    sweep_window,
    utc,
    wants_full_scan,
)

NOW = datetime(2026, 10, 15, 11, 30, tzinfo=timezone.utc)


def test_the_window_snaps_outwards_to_whole_months():
    start, end = sweep_window(NOW, past_days=90, future_days=180)

    assert start == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert end == datetime(2027, 5, 1, tzinfo=timezone.utc)


def test_the_window_holds_still_for_most_of_a_month():
    """A boundary that moved daily would reshuffle every slice under the sweep."""
    first = sweep_window(NOW)
    later = sweep_window(NOW + timedelta(days=5))

    assert first == later


def test_the_window_is_cut_into_whole_months():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2027, 1, 1, tzinfo=timezone.utc)

    assert month_slices(start, end) == [
        (datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc)),
        (datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 12, 1, tzinfo=timezone.utc)),
        (datetime(2026, 12, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)),
    ]


def test_slices_cover_the_window_exactly_and_do_not_overlap():
    start, end = sweep_window(NOW)
    slices = month_slices(start, end)

    assert slices[0][0] == start
    assert slices[-1][1] == end
    assert all(left[1] == right[0] for left, right in zip(slices, slices[1:]))


def test_a_partial_first_month_is_not_widened():
    start = datetime(2026, 10, 20, tzinfo=timezone.utc)
    end = datetime(2026, 12, 1, tzinfo=timezone.utc)

    assert month_slices(start, end)[0] == (start, datetime(2026, 11, 1, tzinfo=timezone.utc))


def test_a_calendar_never_fully_scanned_is_due_at_once():
    assert wants_full_scan(None, NOW) is True


def test_a_full_scan_comes_round_once_a_day():
    assert wants_full_scan(NOW - FULL_SCAN_INTERVAL + timedelta(minutes=1), NOW) is False
    assert wants_full_scan(NOW - FULL_SCAN_INTERVAL, NOW) is True


def test_an_incremental_pass_re_reads_a_little_before_its_last_success():
    """An event updated while the previous pass was in flight must not fall in the gap."""
    assert incremental_floor(NOW) == NOW - timedelta(minutes=10)


def test_a_calendar_with_no_successful_pass_yet_has_no_incremental_floor():
    assert incremental_floor(None) is None


def test_only_a_full_pass_may_conclude_that_something_disappeared():
    """The asymmetry the whole sweep turns on.

    An incremental pass sees only what Google says changed, so everything it did
    not see is merely everything that did not change. Letting it mark rows gone
    would empty the table on the first quiet run.
    """
    assert disappeared_after(NOW, full=True) == NOW
    assert disappeared_after(NOW, full=False) is None


def test_backoff_doubles_and_then_stops_growing():
    assert backoff_until(NOW, 0) == NOW
    assert backoff_until(NOW, 1) == NOW + timedelta(seconds=30)
    assert backoff_until(NOW, 3) == NOW + timedelta(minutes=2)
    assert backoff_until(NOW, 40) == NOW + timedelta(hours=6)


def test_touching_the_window_boundary_is_not_being_in_it():
    start, end = datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc)

    assert occurrence_in_window(start - timedelta(hours=2), start, start, end) is False
    assert occurrence_in_window(end, end + timedelta(hours=2), start, end) is False
    assert occurrence_in_window(start - timedelta(hours=1), start + timedelta(hours=1), start, end) is True


def test_a_title_is_kept_only_for_an_event_that_matched_a_rule():
    """The security boundary of the titles feature, stated as a test."""
    event = {"summary": "Someone's private appointment"}

    assert summary_for(event, matched=False) == ""
    assert summary_for(event, matched=True) == "Someone's private appointment"


def test_a_stored_title_is_trimmed_and_bounded():
    assert summary_for({"summary": "  Spaced  "}, matched=True) == "Spaced"
    assert len(summary_for({"summary": "x" * 500}, matched=True)) == 200


def test_an_event_without_a_usable_title_stores_nothing():
    assert summary_for({}, matched=True) == ""
    assert summary_for({"summary": None}, matched=True) == ""


def test_naive_datetimes_are_refused_rather_than_guessed_at():
    with pytest.raises(ValueError):
        utc(datetime(2026, 10, 15, 11, 30))

    assert utc(datetime(2026, 10, 15, 13, 30, tzinfo=timezone(timedelta(hours=2)))) == NOW
