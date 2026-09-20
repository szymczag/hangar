# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Recognition is an intersection of two calendars, and these are its rules.

The organization's training calendar hides its guest list, which is the ordinary
setting for a shared calendar and which Google honours in the API as well. Every
test here exists because of that: the rule's calendar can say what a training is
and when, and only a trainer's own copy can say whose it is.
"""

from copy import deepcopy

import pytest

from plane.ext.capacity.training_events import (
    event_key,
    own_responses,
    recognized_occurrences,
    training_index,
)

TRAINER = "trainer@example.test"
CALENDAR = "shared@example.test"


def rule_event(**overrides):
    """An event as the rule's calendar returns it: titled, and with no guests."""
    event = {
        "id": "event-1",
        "iCalUID": "training@example.test",
        "status": "confirmed",
        "start": {"dateTime": "2026-09-14T09:00:00+02:00"},
        "end": {"dateTime": "2026-09-14T13:00:00+02:00"},
        "summary": "Network security",
    }
    event.update(overrides)
    return event


def own_copy(response="accepted", **overrides):
    """The same event as the trainer's own calendar returns it: no title."""
    event = {
        "id": "event-1_copy",
        "iCalUID": "training@example.test",
        "status": "confirmed",
        "start": {"dateTime": "2026-09-14T09:00:00+02:00"},
        "end": {"dateTime": "2026-09-14T13:00:00+02:00"},
        "attendees": [{"email": TRAINER, "responseStatus": response}],
    }
    event.update(overrides)
    return event


def recognize(rule_events, own_events, participant=TRAINER):
    index, _ = training_index(rule_events, calendar_id=CALENDAR)
    return recognized_occurrences(index, own_responses(own_events, participant=participant))


def test_a_training_is_recognized_although_the_calendar_hides_its_guest_list():
    # The rule's calendar names no attendees at all -- this is the shape that
    # made the previous implementation recognize one event in a hundred and
    # eighty-eight. Identity comes from the trainer's own copy instead.
    [occurrence] = recognize([rule_event()], [own_copy()])

    assert occurrence["status"] == "confirmed"
    assert set(occurrence) == {"key", "start", "end", "status"}


def test_an_event_nobody_invited_this_trainer_to_is_not_theirs():
    # On the training calendar, so it is a training -- but somebody else's.
    assert recognize([rule_event()], []) == []


def test_an_event_outside_the_rule_calendar_is_never_recognized():
    # The trainer's own calendar is full of things that are not trainings, and
    # none of them may become one just by being in it.
    personal = own_copy(iCalUID="dentist@example.test", id="dentist")

    assert recognize([rule_event()], [personal]) == []


@pytest.mark.parametrize(
    "response, expected",
    [("needsAction", "pending"), ("tentative", "pending"), ("accepted", "confirmed"), ("declined", None)],
)
def test_the_trainers_own_answer_decides_the_status(response, expected):
    result = recognize([rule_event()], [own_copy(response)])

    assert (result[0]["status"] if result else None) == expected


def test_an_unreadable_answer_counts_as_pending_rather_than_vanishing():
    # A guest list Google omits even to its own attendee. Silence is not a
    # refusal: a training somebody has not answered still blocks their time.
    [occurrence] = recognize([rule_event()], [own_copy(attendees=None, attendeesOmitted=True)])

    assert occurrence["status"] == "pending"


def test_a_copy_without_the_trainer_on_it_is_not_recognized():
    # Distinct from the case above: the list is present and this person is not
    # on it, which is a real answer rather than a missing one.
    other = own_copy(attendees=[{"email": "someone@example.test", "responseStatus": "accepted"}])

    assert recognize([rule_event()], [other]) == []


def test_the_two_calendars_agree_on_identity_across_recurrence():
    index, _ = training_index([rule_event()], calendar_id=CALENDAR)
    responses = own_responses([own_copy()], participant=TRAINER)

    assert set(index) == set(responses)

    later = deepcopy(rule_event())
    later["originalStartTime"] = {"dateTime": "2026-09-21T09:00:00+02:00"}

    assert event_key(later, calendar_id=CALENDAR) not in index


def test_identity_does_not_depend_on_which_calendar_it_was_read_from():
    # The whole intersection rests on this: the same occurrence read from the
    # rule's calendar and from "primary" has to produce the same key.
    assert event_key(rule_event(), calendar_id=CALENDAR) == event_key(own_copy(), calendar_id="primary")


def test_cancellations_are_separated_rather_than_indexed():
    index, cancelled = training_index([rule_event(status="cancelled")], calendar_id=CALENDAR)

    assert index == {}
    assert cancelled == {event_key(rule_event(), calendar_id=CALENDAR)}


def test_a_cancelled_copy_in_the_trainers_calendar_yields_nothing():
    assert recognize([rule_event()], [own_copy(status="cancelled")]) == []


def test_all_day_event_has_exclusive_calendar_local_end():
    event = rule_event(start={"date": "2026-03-29"}, end={"date": "2026-03-30"}, calendar_timezone="Europe/Warsaw")
    index, _ = training_index([event], calendar_id=CALENDAR)
    [entry] = index.values()

    assert entry["start"] == "2026-03-29T00:00:00+01:00"
    assert entry["end"] == "2026-03-30T00:00:00+02:00"


def test_a_malformed_event_is_skipped_rather_than_failing_the_sweep():
    # One unusable row on a shared calendar must not cost everybody else their
    # trainings for the rest of the window.
    index, _ = training_index([{"id": "broken"}, rule_event()], calendar_id=CALENDAR)

    assert len(index) == 1


def test_an_event_that_ends_before_it_starts_is_not_indexed():
    reversed_times = rule_event(
        start={"dateTime": "2026-09-14T13:00:00+02:00"},
        end={"dateTime": "2026-09-14T09:00:00+02:00"},
    )
    index, _ = training_index([reversed_times], calendar_id=CALENDAR)

    assert index == {}


def test_the_index_carries_titles_and_the_responses_never_do():
    # The privacy boundary, asserted rather than assumed: titles may only ever
    # arrive from the calendar where every event is a training.
    index, _ = training_index([rule_event()], calendar_id=CALENDAR)
    [entry] = index.values()

    assert entry["summary"] == "Network security"
    assert recognized_occurrences(index, own_responses([own_copy()], participant=TRAINER))[0].keys() == {
        "key",
        "start",
        "end",
        "status",
    }
