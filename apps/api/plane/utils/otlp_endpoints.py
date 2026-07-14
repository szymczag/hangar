# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Shared OTLP endpoint helpers so metrics and traces use the same explicitly
configured collector when both are enabled.
"""

import os
from dataclasses import dataclass
from urllib.parse import urlparse

# When no port in URL: https -> 443 (ingress), http -> 4317 (OTLP gRPC default)
OTLP_GRPC_DEFAULT_PORT = "4317"
HTTPS_DEFAULT_PORT = "443"


@dataclass(frozen=True)
class OTLPMetricExportConfiguration:
    """Resolved metrics-export configuration safe to expose as status only."""

    protocol: str | None
    endpoint: str | None

    @property
    def is_configured(self) -> bool:
        return self.endpoint is not None


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


def get_otlp_metric_export_configuration() -> OTLPMetricExportConfiguration:
    """
    Resolve the configured metrics collector once for both the API status and exporter.

    The endpoint deliberately remains process configuration: callers may expose only
    ``is_configured`` and ``protocol``, never the collector URL.
    """
    protocol = (os.environ.get("OTLP_METRICS_PROTOCOL") or "grpc").strip().lower()
    if protocol not in {"grpc", "http"}:
        return OTLPMetricExportConfiguration(protocol=None, endpoint=None)

    try:
        endpoint = get_otlp_grpc_endpoint() if protocol == "grpc" else get_otlp_http_metrics_url()
    except ValueError:
        endpoint = None

    return OTLPMetricExportConfiguration(protocol=protocol, endpoint=endpoint)
