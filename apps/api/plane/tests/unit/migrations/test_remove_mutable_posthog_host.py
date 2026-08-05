# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from importlib import import_module
from unittest.mock import Mock

import pytest


@pytest.mark.unit
def test_migration_removes_legacy_mutable_posthog_host():
    migration = import_module(
        "plane.license.migrations.0009_remove_mutable_posthog_host"
    )
    historical_configuration = Mock()
    apps = Mock()
    apps.get_model.return_value = historical_configuration

    migration.remove_mutable_posthog_host(apps, schema_editor=None)

    apps.get_model.assert_called_once_with("license", "InstanceConfiguration")
    historical_configuration.objects.filter.assert_called_once_with(
        key="POSTHOG_HOST"
    )
    historical_configuration.objects.filter.return_value.delete.assert_called_once_with()
