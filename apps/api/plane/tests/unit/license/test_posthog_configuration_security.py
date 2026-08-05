# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace

import pytest

from plane.license.api.views.configuration import InstanceConfigurationEndpoint


@pytest.mark.unit
def test_instance_configuration_rejects_posthog_host_updates():
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(
            data={"POSTHOG_HOST": "http://169.254.169.254"},
            user=SimpleNamespace(is_anonymous=True),
        )
    )

    assert response.status_code == 400
    assert response.data == {
        "error": "PostHog destination is managed by the deployment."
    }


@pytest.mark.unit
def test_instance_configuration_hides_legacy_posthog_host(mocker):
    configurations = mocker.Mock()
    exclude = mocker.patch(
        "plane.license.api.views.configuration.InstanceConfiguration.objects.exclude",
        return_value=configurations,
    )
    serializer = mocker.patch(
        "plane.license.api.views.configuration.InstanceConfigurationSerializer"
    )
    serializer.return_value.data = []

    endpoint = InstanceConfigurationEndpoint()
    response = endpoint.get.__wrapped__(endpoint, SimpleNamespace())

    assert response.status_code == 200
    exclude.assert_called_once_with(key__in={"POSTHOG_HOST"})
    serializer.assert_called_once_with(configurations, many=True)
