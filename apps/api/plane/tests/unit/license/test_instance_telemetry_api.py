# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from plane.license.api.views.instance import InstanceEndpoint, InstanceTelemetryEndpoint
from plane.utils.otlp_endpoints import OTLPMetricExportConfiguration


@pytest.mark.unit
def test_instance_api_rejects_telemetry_opt_in_without_a_collector():
    serializer = MagicMock()
    serializer.is_valid.return_value = True
    serializer.validated_data = {"is_telemetry_enabled": True}

    with (
        patch("plane.license.api.views.instance.Instance.objects.first", return_value=MagicMock()),
        patch("plane.license.api.views.instance.InstanceSerializer", return_value=serializer),
        patch(
            "plane.license.api.views.instance.get_otlp_metric_export_configuration",
            return_value=OTLPMetricExportConfiguration(protocol="grpc", endpoint=None),
        ),
    ):
        response = InstanceEndpoint().patch(
            SimpleNamespace(data={"is_telemetry_enabled": True}, user=SimpleNamespace(is_anonymous=True))
        )

    assert response.status_code == 400
    assert response.data == {
        "is_telemetry_enabled": ["Configure a valid OTLP collector in deployment settings before enabling telemetry."]
    }
    serializer.save.assert_not_called()


@pytest.mark.unit
def test_instance_api_allows_telemetry_opt_in_with_a_collector():
    serializer = MagicMock()
    serializer.is_valid.return_value = True
    serializer.validated_data = {"is_telemetry_enabled": True}
    serializer.data = {"is_telemetry_enabled": True}

    with (
        patch("plane.license.api.views.instance.Instance.objects.first", return_value=MagicMock()),
        patch("plane.license.api.views.instance.InstanceSerializer", return_value=serializer),
        patch(
            "plane.license.api.views.instance.get_otlp_metric_export_configuration",
            return_value=OTLPMetricExportConfiguration(protocol="grpc", endpoint="otel.example.com:443"),
        ),
    ):
        response = InstanceEndpoint().patch(
            SimpleNamespace(data={"is_telemetry_enabled": True}, user=SimpleNamespace(is_anonymous=True))
        )

    assert response.status_code == 200
    assert response.data == {"is_telemetry_enabled": True}
    serializer.save.assert_called_once()


@pytest.mark.unit
def test_telemetry_status_does_not_expose_the_collector_url():
    with patch(
        "plane.license.api.views.instance.get_otlp_metric_export_configuration",
        return_value=OTLPMetricExportConfiguration(protocol="http", endpoint="https://otel.example.com/v1/metrics"),
    ):
        response = InstanceTelemetryEndpoint().get(SimpleNamespace())

    assert response.status_code == 200
    assert response.data == {"collector_configured": True, "metrics_protocol": "http"}
