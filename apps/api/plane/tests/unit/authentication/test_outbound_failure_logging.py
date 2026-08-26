# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A failed provider call has to be diagnosable from the logs.

Sign-in answers one code for every failure so it cannot be used to probe the
deployment. That leaves the operator with nothing, and the hardened outbound
transport made it worse: a destination our own egress policy refuses raises the
same exception types as a provider that did not answer. The first is a
deployment problem they can fix; the second is not.

What must never appear is the request itself — the body carries the client
secret and the authorization code, and the headers carry the access token.
"""

import logging

import pytest
import requests

from plane.authentication.adapter.oauth import OauthAdapter
from plane.authentication.utils.outbound import OutboundResponse


class _Adapter:
    """Only the logging helper is under test, so the rest is not constructed."""

    provider = "google"
    logger = logging.getLogger("plane.authentication.test")

    _log_outbound_failure = OauthAdapter._log_outbound_failure


@pytest.mark.unit
def test_a_destination_refused_by_our_own_policy_is_marked_as_such(caplog):
    """The distinction that decides who has to act."""
    with caplog.at_level(logging.WARNING):
        _Adapter()._log_outbound_failure("Token exchange", ValueError("Unsafe outbound URL"))

    record = caplog.records[-1]
    assert record.refused_by_egress_policy is True
    assert "Unsafe outbound URL" in record.getMessage()
    assert "google" in record.getMessage()


@pytest.mark.unit
def test_a_provider_that_did_not_answer_is_not(caplog):
    with caplog.at_level(logging.WARNING):
        _Adapter()._log_outbound_failure("Token exchange", requests.ConnectionError("connection refused"))

    record = caplog.records[-1]
    assert record.refused_by_egress_policy is False
    assert "connection refused" in record.getMessage()


@pytest.mark.unit
def test_an_exception_with_no_message_still_names_its_type(caplog):
    with caplog.at_level(logging.WARNING):
        _Adapter()._log_outbound_failure("User info request", requests.Timeout())

    message = caplog.records[-1].getMessage()
    assert "Timeout" in message
    assert "no detail" in message


@pytest.mark.unit
def test_a_provider_refusal_carries_the_reason_the_provider_gave():
    """invalid_client and redirect_uri_mismatch are the answer, not noise.

    OAuth 2.0 defines these fields precisely so a caller can act on them
    (RFC 6749 section 5.2). Raising only "HTTP 400" turns a provider naming the
    exact misconfiguration into "provider error, try again".
    """
    response = OutboundResponse(
        400, b'{"error": "invalid_client", "error_description": "The OAuth client was not found."}'
    )

    with pytest.raises(requests.HTTPError) as raised:
        response.raise_for_status()

    assert "invalid_client" in str(raised.value)
    assert "The OAuth client was not found." in str(raised.value)


@pytest.mark.unit
def test_only_the_two_standard_fields_are_repeated():
    """The rest of a body is not ours to copy into a log."""
    response = OutboundResponse(
        400,
        b'{"error": "invalid_grant", "id_token": "secret-assertion", "access_token": "secret-token"}',
    )

    with pytest.raises(requests.HTTPError) as raised:
        response.raise_for_status()

    message = str(raised.value)
    assert "invalid_grant" in message
    assert "secret-assertion" not in message
    assert "secret-token" not in message


@pytest.mark.unit
@pytest.mark.parametrize("body", [b"", b"not json", b'"a string"', b"[]"])
def test_a_body_that_says_nothing_useful_is_left_out(body):
    response = OutboundResponse(500, body)

    with pytest.raises(requests.HTTPError) as raised:
        response.raise_for_status()

    assert str(raised.value) == "Provider returned HTTP 500"


@pytest.mark.unit
def test_an_overlong_description_is_truncated():
    response = OutboundResponse(400, b'{"error": "invalid_grant", "error_description": "' + b"x" * 5000 + b'"}')

    with pytest.raises(requests.HTTPError) as raised:
        response.raise_for_status()

    assert len(str(raised.value)) < 400
