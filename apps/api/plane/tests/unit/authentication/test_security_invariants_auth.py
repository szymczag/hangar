# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Authentication controls the fork added, pinned so an upstream sync cannot drop them.

Each test here fails if its control is removed or weakened; FORK.md, "Security
invariants", maps them to the controls (S8, S9, S11, S12).
"""

import importlib
import inspect
import re
import time
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIClient

from plane.authentication import rate_limit
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.authentication.utils import oauth_transaction
from plane.authentication.utils.oauth_transaction import (
    OAUTH_TRANSACTION_TTL,
    consume_oauth_transaction,
    start_oauth_transaction,
)
from plane.authentication.utils.password import PASSWORD_MIN_LENGTH, is_password_strong

pytestmark = pytest.mark.unit


# --- S8: admin second-factor throttles and the single-surface redirect throttle


class TestThrottleAuthRedirect:
    @pytest.mark.parametrize("surfaces", [{}, {"is_app": True, "is_space": True}])
    def test_exactly_one_surface_must_be_selected(self, surfaces):
        with pytest.raises(ValueError, match="exactly one authentication surface"):
            rate_limit.throttle_auth_redirect(**surfaces)


WEBAUTHN_ENDPOINTS = {
    "AdminWebAuthnAuthenticationOptionsEndpoint": "AdminWebAuthnOptionsThrottle",
    "AdminWebAuthnAuthenticationVerifyEndpoint": "AdminWebAuthnVerifyThrottle",
    "AdminWebAuthnRegistrationOptionsEndpoint": "AdminWebAuthnRegisterThrottle",
    "AdminWebAuthnRegistrationVerifyEndpoint": "AdminWebAuthnRegisterThrottle",
}


class TestAdminWebAuthnThrottles:
    @pytest.mark.parametrize("endpoint,throttle", sorted(WEBAUTHN_ENDPOINTS.items()))
    def test_every_second_factor_endpoint_is_throttled(self, endpoint, throttle):
        views = importlib.import_module("plane.ext.views.instance_webauthn")
        throttle_class = getattr(rate_limit, throttle)
        assert getattr(views, endpoint).throttle_classes == [throttle_class]

    @pytest.mark.parametrize("throttle", sorted(set(WEBAUTHN_ENDPOINTS.values())))
    def test_each_throttle_has_its_own_bounded_bucket(self, throttle):
        throttle_class = getattr(rate_limit, throttle)
        # Its own scope, so a failing second-factor loop cannot spend the
        # password step's "authentication" bucket, and a finite rate.
        assert throttle_class.scope.startswith("admin_webauthn_")
        num_requests, duration = throttle_class().parse_rate(throttle_class.rate)
        assert 0 < num_requests <= 60 and duration >= 60

    @pytest.mark.django_db
    def test_repeated_options_requests_are_refused(self):
        cache.clear()
        client = APIClient()
        url = "/api/instances/admins/webauthn/authentication/options/"
        try:
            with patch.object(rate_limit.AdminWebAuthnOptionsThrottle, "rate", "2/minute"):
                statuses = [client.post(url, {}, format="json").status_code for _ in range(3)]
        finally:
            cache.clear()
        assert 429 not in statuses[:2]
        assert statuses[2] == 429


# --- S9: password minimum length


class TestPasswordMinimumLength:
    # A random-looking string zxcvbn scores 4 at any of these lengths, so only
    # the length rule can tell them apart.
    STRONG = "Vq7#mZp2!rLx9@tKw4$hN"

    def test_minimum_is_fifteen(self):
        assert PASSWORD_MIN_LENGTH == 15

    def test_a_strong_fourteen_character_password_is_refused(self):
        assert is_password_strong(self.STRONG[:14]) is False

    def test_a_strong_fifteen_character_password_is_accepted(self):
        assert is_password_strong(self.STRONG[:15]) is True


# --- S11: OAuth transaction: TTL, constant-time compare, per-provider key, single use


def _request():
    request = MagicMock()
    request.session = {}
    return request


class TestOAuthTransaction:
    def test_an_expired_transaction_is_refused(self):
        request = _request()
        state = start_oauth_transaction(request, "provider_app", host="h", next_path="/")
        request.session["provider_app"]["created_at"] = time.time() - OAUTH_TRANSACTION_TTL - 1
        _transaction, valid = consume_oauth_transaction(request, "provider_app", state)
        assert valid is False

    def test_a_transaction_from_the_future_is_refused(self):
        request = _request()
        state = start_oauth_transaction(request, "provider_app", host="h", next_path="/")
        request.session["provider_app"]["created_at"] = time.time() + 60
        assert consume_oauth_transaction(request, "provider_app", state)[1] is False

    def test_a_transaction_without_a_timestamp_is_refused(self):
        request = _request()
        state = start_oauth_transaction(request, "provider_app", host="h", next_path="/")
        del request.session["provider_app"]["created_at"]
        assert consume_oauth_transaction(request, "provider_app", state)[1] is False

    def test_ttl_is_at_most_ten_minutes(self):
        assert 0 < OAUTH_TRANSACTION_TTL <= 600

    def test_state_is_compared_in_constant_time(self):
        request = _request()
        state = start_oauth_transaction(request, "provider_app", host="h", next_path="/")
        with patch.object(oauth_transaction.hmac, "compare_digest", wraps=oauth_transaction.hmac.compare_digest) as spy:
            assert consume_oauth_transaction(request, "provider_app", state)[1] is True
        spy.assert_called_once_with(state, state)

    def test_a_state_issued_for_one_provider_does_not_complete_another(self):
        request = _request()
        state = start_oauth_transaction(request, "github_oauth_transaction_app", host="h", next_path="/")
        assert consume_oauth_transaction(request, "gitlab_oauth_transaction_app", state)[1] is False

    def test_a_failed_attempt_still_consumes_the_transaction(self):
        request = _request()
        state = start_oauth_transaction(request, "provider_app", host="h", next_path="/")
        assert consume_oauth_transaction(request, "provider_app", "forged")[1] is False
        assert consume_oauth_transaction(request, "provider_app", state)[1] is False


PROVIDER_VIEWS = {
    f"plane.authentication.views.{surface}.{provider}": f"{provider.upper()}_TRANSACTION_{surface.upper()}"
    for surface in ("app", "space")
    for provider in ("github", "gitlab", "gitea", "google")
}


class TestOAuthTransactionKeys:
    def test_every_provider_and_surface_has_its_own_key(self):
        keys = [getattr(importlib.import_module(module), name) for module, name in PROVIDER_VIEWS.items()]
        assert len(set(keys)) == len(keys)

    @pytest.mark.parametrize("module,name", sorted(PROVIDER_VIEWS.items()))
    def test_each_view_keeps_its_transaction_under_its_own_key(self, module, name):
        source = inspect.getsource(importlib.import_module(module))
        # Every place the view stores, starts, reads or consumes a transaction
        # names this module's key, never another provider's or surface's.
        uses = re.findall(
            r"(?:start_oauth_transaction\(\s*request,|consume_oauth_transaction\(request,|"
            r"request\.session\[|request\.session\.pop\()\s*(\w+)",
            source,
        )
        assert len(uses) >= 2, f"{module} no longer starts and consumes a transaction"
        assert set(uses) == {name}


# --- S12: CSRF-enforced session authentication


class TestCsrfEnforcedSessionAuthentication:
    def test_an_unsafe_request_without_a_token_is_refused(self):
        django_request = RequestFactory().post("/x/", {}, content_type="application/json")
        django_request.user = MagicMock(is_active=True)
        with pytest.raises(PermissionDenied, match="CSRF"):
            CsrfEnforcedSessionAuthentication().authenticate(Request(django_request))

    def test_an_anonymous_request_is_not_authenticated(self):
        django_request = RequestFactory().post("/x/", {}, content_type="application/json")
        django_request.user = AnonymousUser()
        assert CsrfEnforcedSessionAuthentication().authenticate(Request(django_request)) is None

    @pytest.mark.parametrize(
        "module",
        ["plane.ext.views.capacity_training", "plane.ext.views.capacity_import", "plane.ext.views.workshop_template"],
    )
    def test_the_views_that_opted_in_still_use_it(self, module):
        loaded = importlib.import_module(module)
        users = [
            member
            for _name, member in inspect.getmembers(loaded, inspect.isclass)
            if member.__module__ == loaded.__name__
            and CsrfEnforcedSessionAuthentication in getattr(member, "authentication_classes", ())
        ]
        assert users, f"no view in {module} uses CsrfEnforcedSessionAuthentication any more"
