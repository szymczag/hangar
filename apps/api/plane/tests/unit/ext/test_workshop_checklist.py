# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from plane.ext.services.workshop_checklist import target_date_for

WARSAW = ZoneInfo("Europe/Warsaw")


def test_target_date_is_none_while_the_workshop_has_no_date():
    assert target_date_for(None, -7, WARSAW) is None


def test_offsets_count_backwards_and_forwards_from_the_workshop():
    anchor = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)

    assert target_date_for(anchor, 0, WARSAW) == date(2026, 10, 15)
    assert target_date_for(anchor, -7, WARSAW) == date(2026, 10, 8)
    assert target_date_for(anchor, 1, WARSAW) == date(2026, 10, 16)


def test_the_day_is_the_trainer_s_local_one_not_utc_s():
    """A workshop at 23:30 UTC has already started tomorrow in Warsaw.

    Counting in UTC would date the preparation task a day late for everyone
    actually doing the work.
    """
    anchor = datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc)

    assert target_date_for(anchor, 0, WARSAW) == date(2026, 10, 16)
    assert target_date_for(anchor, 0, ZoneInfo("UTC")) == date(2026, 10, 15)


def test_offsets_cross_a_daylight_saving_boundary_by_calendar_days():
    """Europe/Warsaw leaves summer time on 2026-10-25.

    Counting in fixed 24-hour steps would land a seven-day offset on the 26th,
    because one of those days is 25 hours long. People count days on a calendar,
    so the offset does too.
    """
    anchor = datetime(2026, 11, 1, 10, 0, tzinfo=WARSAW)

    assert target_date_for(anchor, -7, WARSAW) == date(2026, 10, 25)
    assert target_date_for(anchor, -8, WARSAW) == date(2026, 10, 24)


def test_a_workshop_late_in_the_year_rolls_into_the_next_one():
    anchor = datetime(2026, 12, 30, 9, 0, tzinfo=timezone.utc)

    assert target_date_for(anchor, 5, WARSAW) == date(2027, 1, 4)
