# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Setting a first password is rate limited per account and per address.

`POST /auth/set-password/` only answers a signed-in session, and the default
`AnonRateThrottle` skips a signed-in caller, so upstream left it unlimited. It
now carries the pair the email change uses: `SetPasswordThrottle` per account
and `AuthenticationThrottle` per client address. A refusal is 429 with
`RATE_LIMIT_EXCEEDED`, the shape every other auth throttle answers with, and
leaves the account untouched.
"""

import uuid
from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework.throttling import UserRateThrottle

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.authentication.rate_limit import AuthenticationThrottle, SetPasswordThrottle
from plane.authentication.views.common import SetUserPasswordEndpoint
from plane.db.models import Profile, User

SET_URL = "/auth/set-password/"
STRONG = "Tr0ub4dor&3-quite-long"
WEAK = "short"
LIMITED = str(AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"])


@pytest.fixture(autouse=True)
def _fresh_cache():
    # Both throttles count in the cache; a test must not inherit another's.
    cache.clear()
    yield
    cache.clear()


def _autoset_account():
    """A signed-in account that has no password of its own yet."""
    user = User.objects.create(email=f"{uuid.uuid4().hex}@example.com", username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    user.is_password_autoset = True
    user.set_password(uuid.uuid4().hex)
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.contract
def test_the_endpoint_carries_both_throttles():
    assert SetPasswordThrottle in SetUserPasswordEndpoint.throttle_classes
    assert AuthenticationThrottle in SetUserPasswordEndpoint.throttle_classes


@pytest.mark.contract
def test_the_account_limit_is_per_user():
    assert SetPasswordThrottle.scope == "set_password"
    assert issubclass(SetPasswordThrottle, UserRateThrottle)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_account_is_limited_across_attempts():
    client, user = _autoset_account()

    with patch.object(SetPasswordThrottle, "rate", "2/hour"):
        for _ in range(2):
            response = client.post(SET_URL, {"password": WEAK}, format="json")
            assert response.status_code == 400
        limited = client.post(SET_URL, {"password": STRONG}, format="json")

    assert limited.status_code == 429
    assert str(limited.data["error_code"]) == LIMITED
    user.refresh_from_db()
    assert user.is_password_autoset is True, "a throttled request still set the password"
    assert not user.check_password(STRONG)


@pytest.mark.contract
@pytest.mark.django_db
def test_one_account_running_out_does_not_limit_another():
    first, _ = _autoset_account()
    second, other = _autoset_account()

    with patch.object(SetPasswordThrottle, "rate", "1/hour"):
        assert first.post(SET_URL, {"password": WEAK}, format="json").status_code == 400
        assert first.post(SET_URL, {"password": WEAK}, format="json").status_code == 429
        response = second.post(SET_URL, {"password": STRONG}, format="json")

    assert response.status_code == 200
    other.refresh_from_db()
    assert other.check_password(STRONG)


@pytest.mark.contract
@pytest.mark.django_db
def test_one_address_is_limited_across_accounts():
    first, _ = _autoset_account()
    second, other = _autoset_account()

    with patch.object(AuthenticationThrottle, "rate", "1/minute"):
        assert first.post(SET_URL, {"password": WEAK}, format="json").status_code == 400
        limited = second.post(SET_URL, {"password": STRONG}, format="json")

    assert limited.status_code == 429
    assert str(limited.data["error_code"]) == LIMITED
    other.refresh_from_db()
    assert other.is_password_autoset is True
