# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The instance reports the role needed to mint an API token.

The endpoint that creates tokens refuses a membership below the configured role.
The application has to ask the same question before it offers the feature, or it
accepts a form it could have known would be refused — which is what someone hit:
a create button, a filled-in dialog, and an error on save.

The threshold is deliberately one value read from one place. Two copies drift,
and a drifting copy either hides a feature that works or offers one that does
not.
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from plane.license.models import InstanceConfiguration
from plane.utils.api_token_policy import DEFAULT_MINIMUM_ROLE, api_token_minimum_role
from plane.tests.contract.app import test_google_auth as _google_auth

setup_instance = _google_auth.setup_instance


@pytest.fixture(autouse=True)
def _forget_cached_responses():
    """The endpoint's answer is cached, and God Mode invalidates it on save.

    A test that writes configuration directly does not, so without this each
    test would read whatever the one before it left behind.
    """
    cache.clear()
    yield
    cache.clear()


def _configure(value):
    InstanceConfiguration.objects.update_or_create(
        key="API_TOKEN_MINIMUM_ROLE",
        defaults={"value": value, "category": "API", "is_encrypted": False},
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_the_instance_reports_the_threshold(db, setup_instance):
    _configure("15")

    reported = APIClient().get("/api/instances/").data["config"]

    assert reported["api_token_minimum_role"] == 15


@pytest.mark.contract
@pytest.mark.django_db
def test_the_reported_value_is_the_one_the_endpoint_enforces(db, setup_instance):
    """One value, read from one place, so the offer and the refusal agree."""
    _configure("20")

    reported = APIClient().get("/api/instances/").data["config"]

    assert reported["api_token_minimum_role"] == api_token_minimum_role()


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unreadable_setting_does_not_lock_everyone_out(db, setup_instance):
    """It must not hand out tokens freely either, hence the default rather than 0."""
    _configure("not a number")

    assert api_token_minimum_role() == DEFAULT_MINIMUM_ROLE
    assert APIClient().get("/api/instances/").data["config"]["api_token_minimum_role"] == DEFAULT_MINIMUM_ROLE
