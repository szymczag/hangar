# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A new account starts on what the instance considers sensible.

Upstream ships one set of starting preferences for everyone: the week begins on
Sunday, the clock is UTC, the theme follows the system. Reasonable for a hosted
product with users everywhere, wrong for a company in one place, where every new
person changes the same three settings by hand.

These are starting values and not rules — a preference is not a security
boundary. So the tests here are as much about what is left alone as about what
is set.
"""

import uuid

import pytest

from plane.db.models import Profile, User
from plane.license.models import InstanceConfiguration
from plane.utils.account_defaults import default_start_of_week, default_theme


def _configure(key, value, category="PREFERENCES"):
    InstanceConfiguration.objects.update_or_create(
        key=key, defaults={"value": value, "category": category, "is_encrypted": False}
    )


def _account(email="person@corp.com"):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    profile = Profile.objects.create(user=user)
    profile.refresh_from_db()
    user.refresh_from_db()
    return user, profile


@pytest.mark.contract
@pytest.mark.django_db
def test_the_week_starts_where_the_instance_says(db):
    _configure("INSTANCE_DEFAULT_START_OF_WEEK", "1")

    _, profile = _account()

    assert profile.start_of_the_week == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_the_theme_starts_where_the_instance_says(db):
    _configure("INSTANCE_DEFAULT_THEME", "light")

    _, profile = _account()

    assert profile.theme.get("theme") == "light"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_clock_starts_where_the_instance_says(db):
    _configure("INSTANCE_DEFAULT_TIMEZONE", "Europe/Warsaw")

    user, _ = _account()

    assert user.user_timezone == "Europe/Warsaw"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_weekday_that_does_not_exist_falls_back(db):
    """The column has choices and would refuse the row, taking the signup with it."""
    _configure("INSTANCE_DEFAULT_START_OF_WEEK", "9")

    assert default_start_of_week() == 1
    _, profile = _account()
    assert 0 <= profile.start_of_the_week <= 6


@pytest.mark.contract
@pytest.mark.django_db
def test_a_theme_nobody_ships_falls_back(db):
    _configure("INSTANCE_DEFAULT_THEME", "chartreuse")

    assert default_theme() == "light"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_choice_already_made_is_not_overwritten(db):
    """Changing the instance default must not reach back into existing accounts."""
    _configure("INSTANCE_DEFAULT_START_OF_WEEK", "1")
    user = User.objects.create(email="settled@corp.com", username=uuid.uuid4().hex)
    profile = Profile.objects.create(user=user)
    profile.start_of_the_week = 6
    profile.theme = {"theme": "dark"}
    profile.save()

    _configure("INSTANCE_DEFAULT_START_OF_WEEK", "3")
    _configure("INSTANCE_DEFAULT_THEME", "light")
    profile.save()
    profile.refresh_from_db()

    assert profile.start_of_the_week == 6
    assert profile.theme == {"theme": "dark"}
