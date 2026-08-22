# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Password guessing against the God Mode console must be rate limited.

The console holds instance-wide authority, and pinning a domain to an identity
provider does not cover it: it checks the password itself rather than going
through the provider adapters. That makes its password the only control in
front of it, so an unlimited guessing rate is the whole attack.

The application sign-in routes already call authentication_throttle_allows.
This endpoint is a plain Django View rather than a DRF APIView, so the
framework's default AnonRateThrottle does not apply to it either.
"""

import uuid
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from django.test import Client

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.authentication.rate_limit import AuthenticationThrottle
from plane.db.models import User
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth

setup_instance = _google_auth.setup_instance

SIGN_IN_URL = "/api/instances/admins/sign-in/"
PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture(autouse=True)
def clear_throttle_state():
    """The limiter counts per client, so each test starts from a clean slate."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def instance_admin(db, setup_instance):
    admin = User.objects.create(
        email="admin@corp.com",
        username=uuid.uuid4().hex,
        is_password_autoset=False,
    )
    admin.set_password(PASSWORD)
    admin.save()
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    return admin


def _error_code(response):
    query = parse_qs(urlparse(response.url).query)
    return int(query["error_code"][0]) if "error_code" in query else None


def _attempt(client, email, password):
    return client.post(SIGN_IN_URL, {"email": email, "password": password})


def _limit(rate):
    """Pin the throttle rate for one block.

    The deployed rate comes from AUTHENTICATION_RATE_LIMIT and is read when the
    throttle class is imported, so settings overrides cannot reach it. The test
    environment sets it high enough that a real limit would never be observed.
    """
    return patch.object(AuthenticationThrottle, "rate", rate)


@pytest.mark.contract
@pytest.mark.django_db
def test_repeated_wrong_passwords_are_eventually_refused(instance_admin):
    """Guessing must stop being answered long before a password falls."""
    client = Client(HTTP_USER_AGENT="Mozilla/5.0 test")

    with _limit("5/minute"):
        codes = [_error_code(_attempt(client, instance_admin.email, f"wrong-{index}")) for index in range(40)]

    assert AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"] in codes, (
        "God Mode accepted 40 consecutive password guesses without throttling"
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_throttling_is_not_bypassed_by_varying_the_email(instance_admin):
    """Counting per account would let an attacker reset the limit at will."""
    client = Client(HTTP_USER_AGENT="Mozilla/5.0 test")

    with _limit("5/minute"):
        codes = [_error_code(_attempt(client, f"nobody-{index}@corp.com", "guess")) for index in range(40)]

    assert AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"] in codes


@pytest.mark.contract
@pytest.mark.django_db
def test_a_legitimate_sign_in_still_succeeds(instance_admin):
    """The limit must not stand in the way of the real administrator."""
    client = Client(HTTP_USER_AGENT="Mozilla/5.0 test")

    with _limit("1000/minute"):
        response = _attempt(client, instance_admin.email, PASSWORD)

    assert response.status_code == 302
    assert _error_code(response) is None
