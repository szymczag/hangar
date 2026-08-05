# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.test import override_settings

from plane.bgtasks.event_tracking_task import posthogConfiguration


@pytest.mark.unit
@override_settings(POSTHOG_HOST="https://telemetry.example.com")
def test_posthog_destination_comes_from_deployment_settings(mocker):
    get_configuration_value = mocker.patch(
        "plane.bgtasks.event_tracking_task.get_configuration_value",
        return_value=("project-key",),
    )

    assert posthogConfiguration() == (
        "project-key",
        "https://telemetry.example.com",
    )
    assert get_configuration_value.call_args.args[0] == [
        {
            "key": "POSTHOG_API_KEY",
            "default": mocker.ANY,
        }
    ]


@pytest.mark.unit
@override_settings(POSTHOG_HOST=False)
def test_posthog_tracking_stays_disabled_without_deployment_host(mocker):
    mocker.patch(
        "plane.bgtasks.event_tracking_task.get_configuration_value",
        return_value=("project-key",),
    )

    assert posthogConfiguration() == (None, None)
