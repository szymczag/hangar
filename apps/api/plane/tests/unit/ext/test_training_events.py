# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from copy import deepcopy

import pytest

from plane.ext.capacity.training_events import recognized_event
from plane.ext.capacity.google import GoogleCalendarError


def invitation():
    return {
        "id": "event-1",
        "iCalUID": "training@example.test",
        "organizer": {"email": "organizer@example.test"},
        "creator": {"email": "someone-else@example.test"},
        "attendees": [{"email": "trainer@example.test", "responseStatus": "accepted"}],
        "start": {"dateTime": "2026-09-14T09:00:00+02:00"},
        "end": {"dateTime": "2026-09-14T13:00:00+02:00"},
        "summary": "Private title",
        "description": "Private description",
    }


def recognize(event, organizer="organizer@example.test", calendar_id="shared@example.test"):
    return recognized_event(event, organizer=organizer, participant="trainer@example.test", calendar_id=calendar_id)


def test_exact_organizer_and_verified_participant_required():
    event = invitation()
    assert recognize(event)["status"] == "confirmed"
    assert recognize(event, organizer=event["creator"]["email"]) is None
    event["attendees"] = [{"email": "other@example.test", "self": True, "responseStatus": "accepted"}]
    assert recognize(event) is None


@pytest.mark.parametrize(
    "response, expected",
    [("needsAction", "pending"), ("tentative", "pending"), ("accepted", "confirmed"), ("declined", None)],
)
def test_invitation_responses(response, expected):
    event = invitation()
    event["attendees"][0]["responseStatus"] = response
    result = recognize(event)
    assert (result["status"] if result else None) == expected


def test_recurring_occurrences_deduplicate_across_calendars_without_leaking_details():
    event = invitation()
    result = recognize(event)
    assert result["key"] == recognize(event, calendar_id="another-calendar")["key"]
    assert set(result) == {"key", "start", "end", "status"}
    second = deepcopy(event)
    second["originalStartTime"] = {"dateTime": "2026-09-21T09:00:00+02:00"}
    assert recognize(second)["key"] != result["key"]
    event["status"] = "cancelled"
    assert recognize(event) is None


def test_all_day_event_has_exclusive_calendar_local_end():
    event = invitation()
    event.update(start={"date": "2026-03-29"}, end={"date": "2026-03-30"}, calendar_timezone="Europe/Warsaw")
    result = recognize(event)
    assert result["start"] == "2026-03-29T00:00:00+01:00"
    assert result["end"] == "2026-03-30T00:00:00+02:00"


def test_incomplete_attendee_list_fails_closed():
    event = invitation()
    event["attendeesOmitted"] = True
    with pytest.raises(GoogleCalendarError, match="incomplete_event_participants"):
        recognize(event)
