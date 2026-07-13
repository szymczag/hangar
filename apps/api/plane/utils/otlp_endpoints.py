# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Shared OTLP endpoint helpers so metrics and traces use the same explicitly
configured collector when both are enabled.
"""

import os
from urllib.parse import urlparse

# When no port in URL: https -> 443 (ingress), http -> 4317 (OTLP gRPC default)
OTLP_GRPC_DEFAULT_PORT = "4317"
HTTPS_DEFAULT_PORT = "443"


def grpc_endpoint_from_url(url: str) -> str:
    """
    Derive gRPC host:port from OTLP_ENDPOINT URL.
    - https://otel.example.com -> otel.example.com:443 (nginx ingress)
    - otel.example.com:4317 -> otel.example.com:4317 (scheme-less with port)
    - otel.example.com -> otel.example.com:4317 (scheme-less, default gRPC port)
    - Explicit port in URL is always preserved.
    """
    url = url.strip()
    if not url:
        raise ValueError("OTLP endpoint cannot be empty")

    # urlparse needs a scheme to correctly populate hostname/netloc.
    # Scheme-less values like "host:port" are misread as scheme="host", path="port".
    if "://" not in url:
        url = "//" + url
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("OTLP endpoint must include a hostname")
    if parsed.port is not None:
        port = str(parsed.port)
    elif parsed.scheme == "https":
        port = HTTPS_DEFAULT_PORT
    else:
        port = OTLP_GRPC_DEFAULT_PORT
    return f"{host}:{port}"


def get_otlp_grpc_endpoint() -> str | None:
    """
    Return the configured gRPC endpoint, or None when telemetry has no explicit
    destination. Hangar never falls back to a vendor-controlled collector.
    """
    base = os.environ.get("OTLP_ENDPOINT", "").strip()
    if not base:
        return None
    return grpc_endpoint_from_url(base)


def get_otlp_http_metrics_url() -> str | None:
    """Return the configured OTLP HTTP metrics URL, or None when unset."""
    base = os.environ.get("OTLP_ENDPOINT", "").strip()
    if not base:
        return None

    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OTLP HTTP endpoint must be an absolute http(s) URL")
    return f"{base.rstrip('/')}/v1/metrics"
