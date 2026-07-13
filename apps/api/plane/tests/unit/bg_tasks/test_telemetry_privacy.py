# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock, patch

import pytest

from plane.license.bgtasks.telemetry_metrics import _collect_and_push_metrics
from plane.license.models import Instance


@pytest.mark.unit
def test_telemetry_requires_an_explicit_collector(monkeypatch):
    monkeypatch.delenv("OTLP_ENDPOINT", raising=False)
    instance = Mock(is_telemetry_enabled=True)

    with (
        patch.object(Instance.objects, "first", return_value=instance),
        patch(
            "plane.license.bgtasks.telemetry_metrics._create_otlp_metric_exporter"
        ) as create_exporter,
    ):
        _collect_and_push_metrics()

    create_exporter.assert_not_called()
