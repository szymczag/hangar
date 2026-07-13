# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from importlib import import_module
from unittest.mock import Mock

import pytest


@pytest.mark.unit
def test_migration_disables_existing_telemetry_exports():
    migration = import_module("plane.license.migrations.0007_disable_telemetry_by_default")
    historical_instance = Mock()
    apps = Mock()
    apps.get_model.return_value = historical_instance

    migration.disable_existing_telemetry(apps, schema_editor=None)

    apps.get_model.assert_called_once_with("license", "Instance")
    historical_instance.objects.filter.assert_called_once_with(is_telemetry_enabled=True)
    historical_instance.objects.filter.return_value.update.assert_called_once_with(
        is_telemetry_enabled=False
    )
