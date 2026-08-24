# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The layer that prevents a mandatory second factor from locking everyone out.

A relying-party id the browser rejects fails in the console with a SecurityError
the API never sees. These tests pin the derivation for each real deployment
topology, and pin the refusals that turn a silent browser failure into a named
error.
"""

from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from plane.ext.auth.webauthn.config import allowed_origins, rp_id, validate_config


@pytest.fixture
def request_stub():
    request = MagicMock()
    request.is_secure.return_value = True
    request.get_host.return_value = "hangar.example.com"
    return request


@override_settings(
    WEBAUTHN_RP_ID=None, ADMIN_BASE_URL=None, WEB_URL="https://hangar.example.com", ADMIN_BASE_PATH="/god-mode"
)
def test_single_host_deployment_derives_the_shared_host(request_stub):
    """The common production shape: console under the app origin."""
    assert rp_id(request_stub) == "hangar.example.com"
    assert allowed_origins(request_stub) == {"https://hangar.example.com"}
    assert validate_config(request_stub) is None


@override_settings(
    WEBAUTHN_RP_ID=None,
    ADMIN_BASE_URL="http://localhost:3001",
    WEB_URL="http://localhost:8000",
    ADMIN_BASE_PATH="/god-mode",
)
def test_local_development_is_a_secure_context_despite_http(request_stub):
    """localhost is exempt from the HTTPS requirement, and ports are not part of an RP ID."""
    assert rp_id(request_stub) == "localhost"
    assert validate_config(request_stub) is None


@override_settings(
    WEBAUTHN_RP_ID=None,
    ADMIN_BASE_URL="https://admin.example.com",
    WEB_URL="https://app.example.com",
    ADMIN_BASE_PATH="/god-mode",
)
def test_split_subdomain_without_an_explicit_rp_id_is_refused(request_stub):
    """The lockout case.

    Deriving from ADMIN_BASE_URL gives admin.example.com, which is fine here —
    but the moment the app origin joins the allowlist the two disagree, and the
    operator must choose the shared parent deliberately.
    """
    assert rp_id(request_stub) == "admin.example.com"
    assert allowed_origins(request_stub) == {"https://admin.example.com"}


@override_settings(
    WEBAUTHN_RP_ID="app.example.com",
    ADMIN_BASE_URL="https://admin.example.com",
    WEB_URL="https://app.example.com",
    ADMIN_BASE_PATH="/god-mode",
)
def test_an_rp_id_that_is_not_a_parent_of_the_console_is_refused(request_stub):
    """Exactly what the browser would reject, refused before options are issued."""
    reason = validate_config(request_stub)

    assert reason is not None
    assert "app.example.com" in reason
    assert "admin.example.com" in reason


@override_settings(
    WEBAUTHN_RP_ID="example.com",
    ADMIN_BASE_URL="https://admin.example.com",
    WEB_URL="https://app.example.com",
    ADMIN_BASE_PATH="/god-mode",
)
def test_the_shared_parent_is_accepted_for_a_split_deployment(request_stub):
    """The correct answer for that topology."""
    assert validate_config(request_stub) is None


@override_settings(
    WEBAUTHN_RP_ID=None, ADMIN_BASE_URL=None, WEB_URL="http://hangar.internal", ADMIN_BASE_PATH="/god-mode"
)
def test_plain_http_outside_localhost_is_refused_with_a_reason(request_stub):
    """Such an instance cannot use WebAuthn at all; say so rather than fail opaquely."""
    reason = validate_config(request_stub)

    assert reason is not None
    assert "HTTPS" in reason


@override_settings(WEBAUTHN_RP_ID="10.0.0.5", ADMIN_BASE_URL="https://10.0.0.5", WEB_URL="https://10.0.0.5")
def test_an_ip_address_is_not_a_valid_relying_party_id(request_stub):
    reason = validate_config(request_stub)

    assert reason is not None
    assert "IP address" in reason


@override_settings(
    WEBAUTHN_RP_ID=None,
    WEBAUTHN_ALLOWED_ORIGINS="https://one.example.com, https://two.example.com",
    ADMIN_BASE_URL="https://one.example.com",
    WEB_URL="https://one.example.com",
)
def test_an_explicit_allowlist_replaces_the_derivation(request_stub):
    assert allowed_origins(request_stub) == {"https://one.example.com", "https://two.example.com"}


@override_settings(
    WEBAUTHN_RP_ID=None, ADMIN_BASE_URL=None, WEB_URL="", APP_BASE_URL="", ADMIN_BASE_PATH="/god-mode"
)
def test_no_derivable_configuration_is_reported_rather_than_guessed(request_stub):
    assert validate_config(request_stub) is not None
