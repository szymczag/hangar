# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock, patch

import pytest

from plane.license.management.commands.register_instance import Command
from plane.license.models import Instance


@pytest.mark.unit
class TestRegisterInstanceCommand:
    def test_release_discovery_is_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RELEASE_DISCOVERY_URL", raising=False)
        command = Command()

        with patch(
            "plane.license.management.commands.register_instance.requests.get"
        ) as request:
            assert command.check_for_latest_version("v1.2.3") == "v1.2.3"

        request.assert_not_called()

    def test_release_discovery_uses_explicit_endpoint(self, monkeypatch):
        monkeypatch.setenv("RELEASE_DISCOVERY_URL", "https://releases.example.test/latest")
        response = Mock()
        response.json.return_value = {"tag_name": "v1.2.4"}
        command = Command()

        with patch(
            "plane.license.management.commands.register_instance.requests.get",
            return_value=response,
        ) as request:
            assert command.check_for_latest_version("v1.2.3") == "v1.2.4"

        request.assert_called_once_with("https://releases.example.test/latest", timeout=10)
        response.raise_for_status.assert_called_once_with()

    def test_telemetry_task_is_not_enqueued_without_opt_in(self):
        instance = Mock(is_telemetry_enabled=False)
        command = Command()

        with (
            patch.object(Instance.objects, "first", return_value=instance),
            patch.object(command, "check_for_current_version", return_value="v1.2.3"),
            patch.object(command, "check_for_latest_version", return_value="v1.2.3"),
            patch(
                "plane.license.management.commands.register_instance.push_instance_metrics.delay"
            ) as enqueue,
        ):
            command.handle(machine_signature="test-signature")

        enqueue.assert_not_called()

    def test_telemetry_task_is_enqueued_after_explicit_opt_in(self):
        instance = Mock(is_telemetry_enabled=True)
        command = Command()

        with (
            patch.object(Instance.objects, "first", return_value=instance),
            patch.object(command, "check_for_current_version", return_value="v1.2.3"),
            patch.object(command, "check_for_latest_version", return_value="v1.2.3"),
            patch(
                "plane.license.management.commands.register_instance.push_instance_metrics.delay"
            ) as enqueue,
        ):
            command.handle(machine_signature="test-signature")

        enqueue.assert_called_once_with()

    def test_model_default_is_opted_out(self):
        assert Instance._meta.get_field("is_telemetry_enabled").default is False
