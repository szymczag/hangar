# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contracts for the shared identity-provider transport.

Every OAuth and OIDC destination now goes through this module, so these are
the tests that keep address pinning, redirect refusal, and the response cap
from regressing for all of them at once.
"""

import ipaddress
import ssl
from unittest.mock import Mock

import pytest
import requests
from django.test import override_settings

from plane.authentication.utils.outbound import (
    OutboundResponse,
    TLSPolicy,
    _connect_pinned,
    checked_response,
    parse_outbound_base_url,
    validate_outbound_url,
)


@pytest.fixture
def public_dns(mocker):
    """Transport contracts are deterministic and never perform real lookups."""
    return mocker.patch(
        "plane.authentication.utils.outbound._getaddrinfo",
        return_value=[(2, 1, 6, "", ("8.8.8.8", 443))],
    )


@override_settings(DEBUG=False)
@pytest.mark.parametrize(
    "url",
    [
        "http://idp.test/oauth",
        "https://user:password@idp.test/oauth",
        "https://idp.test/oauth#fragment",
        "https://idp.test\\@127.0.0.1",
        "https://idp.test/oauth\x01",
        "ftp://idp.test/oauth",
        "https:///oauth",
    ],
)
def test_base_url_shape_is_rejected_without_dns(url):
    with pytest.raises(ValueError):
        parse_outbound_base_url(url)


@override_settings(DEBUG=False)
def test_base_url_query_is_refused_when_disallowed():
    # A query on a configured base URL would be carried into every derived
    # endpoint, so providers that build endpoints from it forbid one.
    parse_outbound_base_url("https://idp.test/oauth?a=b")
    with pytest.raises(ValueError):
        parse_outbound_base_url("https://idp.test/oauth?a=b", allow_query=False)


@override_settings(DEBUG=False)
@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.0.2.1", "fd00::1", "::ffff:127.0.0.1"],
)
def test_non_public_destinations_are_rejected_by_default(public_dns, address):
    family = 10 if ":" in address else 2
    sockaddr = (address, 443, 0, 0) if family == 10 else (address, 443)
    public_dns.return_value = [(family, 1, 6, "", sockaddr)]

    with pytest.raises(ValueError):
        validate_outbound_url("https://internal.test/oauth")


@override_settings(DEBUG=False)
def test_private_destination_is_reachable_only_when_operator_allows_it(public_dns):
    """Self-managed GitLab and Gitea live on internal networks.

    Without an explicit allowlist they must stay unreachable; with one, the
    address is accepted but still pinned.
    """
    public_dns.return_value = [(2, 1, 6, "", ("10.0.0.5", 443))]

    with pytest.raises(ValueError):
        validate_outbound_url("https://internal-gitlab.test/oauth")

    target = validate_outbound_url(
        "https://internal-gitlab.test/oauth",
        allowed_ips=[ipaddress.ip_network("10.0.0.0/8")],
    )
    assert str(target.addresses[0].ip) == "10.0.0.5"

    by_host = validate_outbound_url(
        "https://internal-gitlab.test/oauth",
        allowed_hosts=["internal-gitlab.test"],
    )
    assert str(by_host.addresses[0].ip) == "10.0.0.5"


@override_settings(DEBUG=False)
def test_allowlist_does_not_admit_an_unrelated_host(public_dns):
    public_dns.return_value = [(2, 1, 6, "", ("10.0.0.5", 443))]

    with pytest.raises(ValueError):
        validate_outbound_url("https://other.test/oauth", allowed_hosts=["internal-gitlab.test"])


@override_settings(DEBUG=False)
def test_mixed_public_and_private_answers_are_rejected(public_dns):
    public_dns.return_value = [
        (2, 1, 6, "", ("8.8.8.8", 443)),
        (2, 1, 6, "", ("10.0.0.1", 443)),
    ]

    with pytest.raises(ValueError):
        validate_outbound_url("https://idp.test/oauth")


@override_settings(DEBUG=False)
def test_connection_is_pinned_to_the_validated_address_without_a_second_lookup(public_dns, mocker):
    target = validate_outbound_url("https://idp.test/oauth")
    # A rebinding attempt: the name now resolves to loopback, but the pinned
    # address is what the socket must use.
    public_dns.return_value = [(2, 1, 6, "", ("127.0.0.1", 443))]
    raw_socket = Mock()
    raw_socket.getpeername.return_value = ("8.8.8.8", 443)
    mocker.patch("plane.authentication.utils.outbound.socket.socket", return_value=raw_socket)
    tls_context = mocker.patch("plane.authentication.utils.outbound.ssl.create_default_context").return_value
    tls_context.wrap_socket.return_value = raw_socket

    connected = _connect_pinned(target, target.addresses[0], 10, TLSPolicy.MIN_TLS12)

    assert connected is raw_socket
    raw_socket.connect.assert_called_once_with(("8.8.8.8", 443))
    assert public_dns.call_count == 1


@override_settings(DEBUG=False)
def test_peer_that_differs_from_the_validated_address_is_refused(public_dns, mocker):
    """The check that actually defeats rebinding at connect time."""
    target = validate_outbound_url("https://idp.test/oauth")
    raw_socket = Mock()
    raw_socket.getpeername.return_value = ("127.0.0.1", 443)
    mocker.patch("plane.authentication.utils.outbound.socket.socket", return_value=raw_socket)

    with pytest.raises(OSError):
        _connect_pinned(target, target.addresses[0], 10, TLSPolicy.MIN_TLS12)

    raw_socket.close.assert_called_once()


@override_settings(DEBUG=False)
@pytest.mark.parametrize(
    ("policy", "expected_minimum", "expected_maximum"),
    [
        (TLSPolicy.STRICT_TLS13, ssl.TLSVersion.TLSv1_3, ssl.TLSVersion.TLSv1_3),
        (TLSPolicy.MIN_TLS12, ssl.TLSVersion.TLSv1_2, None),
    ],
)
def test_tls_policy_is_applied_per_provider(public_dns, mocker, policy, expected_minimum, expected_maximum):
    """OIDC pins 1.3 exactly; OAuth allows 1.2 for self-managed hosts."""
    target = validate_outbound_url("https://idp.test/oauth")
    raw_socket = Mock()
    raw_socket.getpeername.return_value = ("8.8.8.8", 443)
    mocker.patch("plane.authentication.utils.outbound.socket.socket", return_value=raw_socket)
    tls_context = mocker.patch("plane.authentication.utils.outbound.ssl.create_default_context").return_value
    tls_context.wrap_socket.return_value = raw_socket

    _connect_pinned(target, target.addresses[0], 10, policy)

    assert tls_context.minimum_version == expected_minimum
    if expected_maximum is not None:
        assert tls_context.maximum_version == expected_maximum


@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
def test_redirects_are_refused_rather_than_followed(status_code):
    with pytest.raises(requests.RequestException):
        checked_response(OutboundResponse(status_code, b""))


def test_error_statuses_raise():
    with pytest.raises(requests.HTTPError):
        checked_response(OutboundResponse(500, b""))


@override_settings(DEBUG=False)
def test_required_origin_pins_a_derived_endpoint_to_its_host(public_dns):
    target = validate_outbound_url("https://idp.test/oauth")

    validate_outbound_url("https://idp.test/token", required_origin=target.origin)
    with pytest.raises(ValueError):
        validate_outbound_url("https://elsewhere.test/token", required_origin=target.origin)


@override_settings(DEBUG=False)
def test_a_host_answering_with_many_addresses_is_reachable(public_dns):
    """www.googleapis.com answers with eight A and eight AAAA records.

    Refusing a host for returning more addresses than we intend to try rejected
    real providers. It broke Google sign-in at the userinfo step, where the
    token exchange had already succeeded — so the account existed, the code was
    valid, and the failure looked like the provider's.
    """
    public_dns.return_value = [(2, 1, 6, "", (f"142.251.127.{octet}", 443)) for octet in range(1, 9)] + [
        (10, 1, 6, "", (f"2a00:1450:4001:80f::{octet}", 443, 0, 0)) for octet in range(1, 9)
    ]

    target = validate_outbound_url("https://www.googleapis.com/oauth2/v3/certs")

    assert len(target.addresses) == 8
    assert str(target.addresses[0].ip) == "142.251.127.1"


@override_settings(DEBUG=False)
def test_a_private_address_anywhere_in_a_long_answer_still_refuses_all_of_it(public_dns):
    """The cap must not become a way to hide a rebinding attempt behind padding.

    Every answer is examined; only how many are carried forward to connect with
    is limited.
    """
    public_dns.return_value = [(2, 1, 6, "", (f"8.8.8.{octet}", 443)) for octet in range(1, 12)] + [
        (2, 1, 6, "", ("10.0.0.1", 443))
    ]

    with pytest.raises(ValueError):
        validate_outbound_url("https://idp.test/oauth")


@override_settings(DEBUG=False)
def test_an_answer_beyond_all_reason_is_still_refused(public_dns):
    """A resolver returning hundreds of addresses is not a provider."""
    public_dns.return_value = [
        (2, 1, 6, "", (f"8.8.{block}.{octet}", 443)) for block in range(4) for octet in range(20)
    ]

    with pytest.raises(ValueError):
        validate_outbound_url("https://idp.test/oauth")
