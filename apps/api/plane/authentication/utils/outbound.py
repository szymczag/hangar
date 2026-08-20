# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validated outbound HTTP for identity providers.

Authentication traffic carries client secrets, bearer tokens, and identity
assertions to hosts an operator configures, so the ordinary HTTP client is the
wrong tool: it re-resolves DNS at connect time, follows redirects, accepts any
TLS version the peer offers, and reads an unbounded body.

This module closes those in one place. A destination is resolved once and every
resolved address is checked against the blocked-network policy; the connection
is then pinned to a validated address and the peer is re-checked after connect,
so a name that resolves to a public address during validation cannot be swung
to a private one before the socket opens. Redirects are refused rather than
followed, responses are capped, and every request carries a deadline.

Originally written for the OIDC provider; extracted so the OAuth providers can
share it instead of each carrying a different subset of the protections.
"""

# Python imports
import http.client
import ipaddress
import json
import socket
import ssl
import time
from dataclasses import dataclass
from socket import getaddrinfo as _getaddrinfo
from urllib.parse import urlencode, urlparse, urlunparse

# Third party imports
import requests

# Django imports
from django.conf import settings

# Module imports
from plane.utils.ip_address import is_blocked_ip

DEFAULT_TIMEOUT = 10
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
MAX_RESOLVED_ADDRESSES = 8


class TLSPolicy:
    """Minimum TLS version a destination must negotiate.

    OIDC pins 1.3 exactly: it is a greenfield integration in this fork, so
    there is no deployment to break and no reason to leave a downgrade path for
    traffic carrying id_tokens. The OAuth providers allow 1.2 because their
    hosts include self-managed GitLab and Gitea installations that predate any
    such requirement — refusing them outright would break working instances to
    defend against an attacker who must already control the network path.
    """

    STRICT_TLS13 = "tls13"
    MIN_TLS12 = "tls12"


@dataclass(frozen=True)
class ResolvedAddress:
    family: int
    socktype: int
    protocol: int
    sockaddr: tuple
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass(frozen=True)
class ResolvedTarget:
    url: str
    parsed: object
    scheme: str
    hostname: str
    port: int
    origin: tuple[str, str, int]
    addresses: tuple[ResolvedAddress, ...]


class OutboundResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"Provider returned HTTP {self.status_code}")

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def _normalize_hostname(hostname):
    if "%" in hostname:
        raise ValueError("Scoped IPv6 addresses are not allowed")
    return hostname.encode("idna").decode("ascii").lower()


def _normalize_ip(address):
    parsed = ipaddress.ip_address(address.split("%", 1)[0])
    return parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped else parsed


def _url_origin(parsed):
    default_port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, _normalize_hostname(parsed.hostname), parsed.port or default_port


def parse_outbound_base_url(url, *, allow_query=True):
    """Validate the shape of a configured URL and return ``(parsed, origin)``.

    No DNS here. Providers call this while constructing themselves, where a
    resolver failure would be reported as a misconfiguration and where a
    lookup per construction would be wasteful. Resolution and the address
    policy are applied later, per request, by ``validate_outbound_url``.
    """
    parsed = urlparse(url)
    if (
        parsed.scheme not in ({"https", "http"} if settings.DEBUG else {"https"})
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or "\\" in (url or "")
        or any(ord(character) < 0x20 for character in (url or ""))
    ):
        raise ValueError("Unsafe outbound URL")
    if parsed.scheme == "http" and not settings.DEBUG:
        raise ValueError("Plaintext HTTP is only allowed in development")
    if parsed.query and not allow_query:
        raise ValueError("Outbound base URL must not carry a query string")
    return parsed, _url_origin(parsed)


def _address_permitted(address, allowed_ips):
    if address.is_global and not is_blocked_ip(address):
        return True
    # Self-managed identity providers legitimately live on private networks.
    # They are reachable only when an operator names the network explicitly,
    # so the default remains public-only.
    return any(address in network for network in (allowed_ips or ()))


def validate_outbound_url(url, *, required_origin=None, allow_query=True, allowed_ips=None, allowed_hosts=None):
    """Resolve and validate the exact socket addresses a request may use.

    ``required_origin`` pins the URL to an origin established earlier, so a
    value taken from a provider's own response cannot move the request to a
    different host. ``allow_query`` is for configured base URLs, where a query
    string is never legitimate and usually indicates an attempt to smuggle
    parameters into a derived endpoint.

    ``allowed_ips`` and ``allowed_hosts`` carry an operator's explicit decision
    to trust an internal destination, matching the semantics already used for
    Gitea. Without them only public addresses are reachable. Address pinning
    and the peer re-check still apply to trusted destinations: an allowlist
    widens which addresses are acceptable, it does not disable validation.
    """
    try:
        parsed, origin = parse_outbound_base_url(url, allow_query=allow_query)
        if required_origin is not None and origin != required_origin:
            raise ValueError("Outbound endpoint origin does not match the expected host")

        hostname = origin[1]
        port = origin[2]
        trusted_host = bool(allowed_hosts) and hostname in {
            (host or "").rstrip(".").lower() for host in allowed_hosts if host
        }
        answers = _getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not answers:
            raise ValueError("Hostname did not resolve")
        resolved = []
        seen = set()
        for family, socktype, protocol, _, sockaddr in answers:
            if family not in (socket.AF_INET, socket.AF_INET6) or socktype != socket.SOCK_STREAM:
                raise ValueError("Hostname returned an unsupported address")
            if sockaddr[1] != port:
                raise ValueError("Resolver returned an unexpected port")
            address = _normalize_ip(sockaddr[0])
            if not trusted_host and not _address_permitted(address, allowed_ips):
                raise ValueError("Hostname resolves to a non-public address")
            key = (family, sockaddr)
            if key not in seen:
                seen.add(key)
                resolved.append(ResolvedAddress(family, socktype, protocol, sockaddr, address))
        if len(resolved) > MAX_RESOLVED_ADDRESSES:
            raise ValueError("Hostname returned too many addresses")
    except (OSError, ValueError) as exc:
        raise ValueError("Unsafe outbound URL") from exc
    return ResolvedTarget(url, parsed, parsed.scheme, hostname, port, origin, tuple(resolved))


def checked_response(response):
    if 300 <= response.status_code < 400:
        raise requests.RequestException("Outbound redirects are not allowed")
    response.raise_for_status()
    return response


def _tls_context(tls_policy):
    context = ssl.create_default_context()
    if tls_policy == TLSPolicy.STRICT_TLS13:
        # Pinning both bounds keeps local OpenSSL policy or a provider's
        # protocol negotiation from silently falling back below 1.3.
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
    else:
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def _connect_pinned(target, address, timeout, tls_policy):
    raw_socket = socket.socket(address.family, address.socktype, address.protocol)
    raw_socket.settimeout(timeout)
    try:
        raw_socket.connect(address.sockaddr)
        peer_ip = _normalize_ip(raw_socket.getpeername()[0])
        if peer_ip != address.ip:
            raise OSError("Connection peer does not match the validated address")
        if target.scheme == "https":
            raw_socket = _tls_context(tls_policy).wrap_socket(raw_socket, server_hostname=target.hostname)
        return raw_socket
    except Exception:
        raw_socket.close()
        raise


def request_validated(
    method,
    target,
    *,
    data=None,
    headers=None,
    timeout=DEFAULT_TIMEOUT,
    max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
    tls_policy=TLSPolicy.MIN_TLS12,
):
    """Perform one request against an already-validated target."""
    body = None
    request_headers = {"Accept": "application/json", "Connection": "close", **(headers or {})}
    if data is not None:
        body = urlencode(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    path = urlunparse(("", "", target.parsed.path or "/", target.parsed.params, target.parsed.query, ""))
    last_error = None
    deadline = time.monotonic() + timeout
    for address in target.addresses:
        connection = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            connection_class = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
            connection = connection_class(target.hostname, target.port, timeout=remaining)
            connection.sock = _connect_pinned(target, address, remaining, tls_policy)
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            # Never reuse `body` here. Any raise below is caught by the retry
            # handler, so overwriting it would send this response back out as
            # the next attempt's request body.
            response_bytes = response.read(max_response_bytes + 1)
            if len(response_bytes) > max_response_bytes:
                raise requests.RequestException("Outbound response is too large")
            result = OutboundResponse(response.status, response_bytes)
            return checked_response(result)
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            if connection is not None:
                connection.close()
    raise requests.ConnectionError("Unable to connect to the validated destination") from last_error


def fetch_validated(method, url, *, required_origin=None, allowed_ips=None, allowed_hosts=None, **kwargs):
    """Validate ``url`` and perform the request in one step."""
    target = validate_outbound_url(
        url,
        required_origin=required_origin,
        allowed_ips=allowed_ips,
        allowed_hosts=allowed_hosts,
    )
    return request_validated(method, target, **kwargs)
