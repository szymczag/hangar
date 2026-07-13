# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.utils.otlp_endpoints import get_otlp_grpc_endpoint, get_otlp_http_metrics_url


@pytest.mark.unit
def test_otlp_endpoints_have_no_external_default(monkeypatch):
    monkeypatch.delenv("OTLP_ENDPOINT", raising=False)

    with pytest.raises(ValueError, match="configured explicitly"):
        get_otlp_grpc_endpoint()

    with pytest.raises(ValueError, match="configured explicitly"):
        get_otlp_http_metrics_url()


@pytest.mark.unit
def test_otlp_endpoints_use_explicit_https_collector(monkeypatch):
    monkeypatch.setenv("OTLP_ENDPOINT", "https://otel.example.test")

    assert get_otlp_grpc_endpoint() == "otel.example.test:443"
    assert get_otlp_http_metrics_url() == "https://otel.example.test/v1/metrics"
