# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What a new account starts with, decided by the instance rather than upstream.

Plane ships one set of starting preferences for everyone: the week begins on
Sunday, the clock is UTC, and the theme follows the system. Those are reasonable
defaults for a hosted product with users everywhere and wrong for a company in
one place, where every new person changes the same three settings by hand.

These are starting values, not rules. Somebody who wants a dark theme still sets
one — a preference is not a security boundary, and forcing it would take
something away from people who need it without protecting anything.
"""

import os

from plane.license.utils.instance_value import get_configuration_value

DEFAULT_START_OF_WEEK = "1"  # Monday. Upstream starts on Sunday.
DEFAULT_THEME = "light"
DEFAULT_TIMEZONE = "UTC"

VALID_THEMES = {"light", "dark", "light-contrast", "dark-contrast", "system", "custom"}


def _read(key: str, fallback: str) -> str:
    (value,) = get_configuration_value([{"key": key, "default": os.environ.get(key, fallback)}])
    return str(value or "").strip()


def default_start_of_week() -> int:
    """Weekday a new account's calendar begins on, 0 for Sunday through 6."""
    raw = _read("INSTANCE_DEFAULT_START_OF_WEEK", DEFAULT_START_OF_WEEK)
    try:
        day = int(raw)
    except (TypeError, ValueError):
        return int(DEFAULT_START_OF_WEEK)
    # An unreadable setting must not produce a weekday that does not exist; the
    # column is a small integer with choices and would refuse the row.
    return day if 0 <= day <= 6 else int(DEFAULT_START_OF_WEEK)


def default_theme() -> str:
    """Theme a new account starts on. Empty means "whatever upstream does"."""
    theme = _read("INSTANCE_DEFAULT_THEME", DEFAULT_THEME).lower()
    return theme if theme in VALID_THEMES else DEFAULT_THEME


def default_timezone() -> str:
    """Timezone a new account starts in, as an IANA name."""
    return _read("INSTANCE_DEFAULT_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
