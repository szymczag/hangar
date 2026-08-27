# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.test import override_settings

from plane.license.api.views.configuration import InstanceConfigurationEndpoint


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=True)
def test_default_workspace_rejects_an_unknown_uuid(mocker):
    workspace_query = mocker.patch("plane.license.api.views.configuration.Workspace.objects.filter")
    workspace_query.return_value.exists.return_value = False

    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(
            data={"INSTANCE_DEFAULT_WORKSPACE_ID": str(uuid4())},
            user=SimpleNamespace(is_anonymous=True),
        )
    )

    assert response.status_code == 400
    assert "does not exist" in response.data["error"]


@pytest.mark.unit
@override_settings(SKIP_ENV_VAR=True)
def test_default_workspace_rejects_a_malformed_uuid():
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(
            data={"INSTANCE_DEFAULT_WORKSPACE_ID": "not-a-workspace"},
            user=SimpleNamespace(is_anonymous=True),
        )
    )

    assert response.status_code == 400
    assert "not valid" in response.data["error"]
