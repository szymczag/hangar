# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The panel must be able to tell an admin where settings actually come from.

With SKIP_ENV_VAR off, stored configuration is never read back — the
environment decides. Every form in the admin panel would still render and
still submit, so without this an admin would save a change, see a success
toast, and get no effect at all.
"""

from types import SimpleNamespace

import pytest
from django.test import override_settings

from plane.license.api.views.configuration import InstanceConfigurationEndpoint


def _get(mocker):
    mocker.patch("plane.license.api.views.configuration.InstanceConfiguration.objects.exclude")
    serializer = mocker.patch("plane.license.api.views.configuration.InstanceConfigurationSerializer")
    serializer.return_value.data = []
    endpoint = InstanceConfigurationEndpoint()
    return endpoint.get.__wrapped__(endpoint, SimpleNamespace())


def _source_of(response):
    return next(item["value"] for item in response.data if item["key"] == "CONFIGURATION_SOURCE")


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=True)
def test_reports_database_when_stored_configuration_is_authoritative(mocker):
    assert _source_of(_get(mocker)) == "database"


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=False)
def test_reports_environment_when_the_deployment_decides(mocker):
    assert _source_of(_get(mocker)) == "environment"


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=False)
def test_refuses_writes_that_could_never_take_effect():
    """Refusing beats reporting success for a change nothing will read."""
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(data={"SSO_ENFORCED_DOMAINS": "corp.com=google"}, user=SimpleNamespace(is_anonymous=True))
    )

    assert response.status_code == 409
    assert "environment variables" in response.data["error"]


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=True)
def test_configuration_source_cannot_be_set_by_an_admin():
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(data={"CONFIGURATION_SOURCE": "database"}, user=SimpleNamespace(is_anonymous=True))
    )

    assert response.status_code == 400


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=True)
@pytest.mark.parametrize(
    "key",
    ["GITEA_ALLOWED_IPS", "GITEA_ALLOWED_HOSTS", "GITLAB_ALLOWED_IPS", "GITLAB_ALLOWED_HOSTS"],
)
def test_provider_network_allowlists_stay_deployment_owned(key):
    """These permit credential-bearing requests to private addresses.

    Anyone with panel access could otherwise aim authentication traffic into
    the internal network, so they belong to whoever owns the deployment.
    """
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(data={key: "10.0.0.0/8"}, user=SimpleNamespace(is_anonymous=True))
    )

    assert response.status_code == 400
    assert "deployment-owned" in response.data["error"]


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(SKIP_ENV_VAR=True)
def test_a_key_this_instance_does_not_store_is_refused_by_name():
    """Silence here reads as success and reverts the control with no reason.

    The endpoint updates the rows it finds, so a key with no row used to answer
    200 while changing nothing — the panel then put its switch back and left the
    administrator to guess why.
    """
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(data={"NOT_A_REAL_SETTING": "1"}, user=SimpleNamespace(is_anonymous=True))
    )

    assert response.status_code == 400
    assert "NOT_A_REAL_SETTING" in response.data["error"]


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(SKIP_ENV_VAR=True)
def test_one_unknown_key_stops_the_whole_write():
    """Half-applying a form is worse than refusing it."""
    from plane.license.models import InstanceConfiguration

    InstanceConfiguration.objects.create(key="SSO_ENFORCED_DOMAINS", value="", category="SSO", is_encrypted=False)

    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(
            data={"SSO_ENFORCED_DOMAINS": "corp.com=google", "NOT_A_REAL_SETTING": "1"},
            user=SimpleNamespace(is_anonymous=True),
        )
    )

    assert response.status_code == 400
    assert InstanceConfiguration.objects.get(key="SSO_ENFORCED_DOMAINS").value == ""
