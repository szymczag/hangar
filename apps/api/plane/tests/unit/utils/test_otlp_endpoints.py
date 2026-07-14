# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.utils.otlp_endpoints import (
    get_otlp_metric_export_configuration,
    get_otlp_grpc_endpoint,
    get_otlp_http_metrics_url,
    grpc_endpoint_from_url,
)


@pytest.mark.unit
class TestOTLPEndpoints:
    def test_no_vendor_fallback_when_endpoint_is_unset(self, monkeypatch):
        monkeypatch.delenv("OTLP_ENDPOINT", raising=False)

        assert get_otlp_grpc_endpoint() is None
        assert get_otlp_http_metrics_url() is None

    def test_blank_endpoint_is_disabled(self, monkeypatch):
        monkeypatch.setenv("OTLP_ENDPOINT", "  ")

        assert get_otlp_grpc_endpoint() is None
        assert get_otlp_http_metrics_url() is None

    @pytest.mark.parametrize(
        ("configured", "expected"),
        [
            ("https://otel.example.com", "otel.example.com:443"),
            ("https://otel.example.com:4317", "otel.example.com:4317"),
            ("otel.example.com", "otel.example.com:4317"),
            ("otel.example.com:4318", "otel.example.com:4318"),
        ],
    )
    def test_grpc_endpoint_is_derived_only_from_explicit_config(self, configured, expected):
        assert grpc_endpoint_from_url(configured) == expected

    def test_empty_grpc_endpoint_is_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            grpc_endpoint_from_url("")

    @pytest.mark.parametrize("configured", ["collector.example.com", "grpc://collector.example.com"])
    def test_http_export_requires_an_absolute_http_url(self, monkeypatch, configured):
        monkeypatch.setenv("OTLP_ENDPOINT", configured)

        with pytest.raises(ValueError, match="absolute http"):
            get_otlp_http_metrics_url()

    def test_http_metrics_path_is_appended(self, monkeypatch):
        monkeypatch.setenv("OTLP_ENDPOINT", "https://otel.example.com/root/")

        assert get_otlp_http_metrics_url() == "https://otel.example.com/root/v1/metrics"

    def test_metrics_configuration_resolves_grpc_collector(self, monkeypatch):
        monkeypatch.setenv("OTLP_ENDPOINT", "https://otel.example.com")
        monkeypatch.setenv("OTLP_METRICS_PROTOCOL", "grpc")

        configuration = get_otlp_metric_export_configuration()

        assert configuration.is_configured is True
        assert configuration.protocol == "grpc"
        assert configuration.endpoint == "otel.example.com:443"

    def test_metrics_configuration_resolves_http_collector(self, monkeypatch):
        monkeypatch.setenv("OTLP_ENDPOINT", "https://otel.example.com/root")
        monkeypatch.setenv("OTLP_METRICS_PROTOCOL", "http")

        configuration = get_otlp_metric_export_configuration()

        assert configuration.is_configured is True
        assert configuration.protocol == "http"
        assert configuration.endpoint == "https://otel.example.com/root/v1/metrics"

    @pytest.mark.parametrize(
        ("endpoint", "protocol"),
        [
            ("", "grpc"),
            ("collector.example.com", "http"),
            ("https://otel.example.com", "unknown"),
        ],
    )
    def test_metrics_configuration_fails_closed_for_invalid_collector(self, monkeypatch, endpoint, protocol):
        monkeypatch.setenv("OTLP_ENDPOINT", endpoint)
        monkeypatch.setenv("OTLP_METRICS_PROTOCOL", protocol)

        configuration = get_otlp_metric_export_configuration()

        assert configuration.is_configured is False
