# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import MagicMock

import pytest
import requests
from django.test import override_settings

from plane.authentication.adapter.error import AuthenticationException
from plane.authentication.provider.oauth.gitea import (
    GITEA_RESPONSE_MAX_BYTES,
    GiteaOAuthProvider,
)


def _provider(mocker, host):
    mocker.patch(
        "plane.authentication.provider.oauth.gitea.get_configuration_value",
        return_value=("client-id", "client-secret", host),
    )
    request = MagicMock()
    request.is_secure.return_value = True
    request.get_host.return_value = "hangar.example.com"
    return GiteaOAuthProvider(request=request, state="state")


@pytest.mark.parametrize(
    "host",
    [
        "http://gitea.example.com",
        "https://user:password@gitea.example.com",
        "https://gitea.example.com/?target=https://internal.example",
        "https://gitea.example.com/#fragment",
        "https://gitea.example.com\\@127.0.0.1",
    ],
)
@override_settings(DEBUG=False)
def test_gitea_rejects_unsafe_base_urls(mocker, host):
    with pytest.raises(AuthenticationException):
        _provider(mocker, host)


@override_settings(DEBUG=False)
def test_gitea_normalizes_origin_and_preserves_subpath(mocker):
    provider = _provider(mocker, "https://GITEA.EXAMPLE.COM:8443/code/")

    assert provider.token_url == "https://gitea.example.com:8443/code/login/oauth/access_token"
    assert provider.userinfo_url == "https://gitea.example.com:8443/code/api/v1/user"


@override_settings(
    GITEA_ALLOWED_IPS=[],
    GITEA_ALLOWED_HOSTS=["trusted-gitea.internal"],
)
def test_gitea_transport_is_pinned_bounded_and_does_not_follow_redirects(mocker):
    response = MagicMock(status_code=200)
    response.iter_content.return_value = [b'{"ok": true}']
    pinned_fetch = mocker.patch(
        "plane.authentication.provider.oauth.gitea.pinned_fetch",
        return_value=response,
    )

    result = GiteaOAuthProvider._request_json(
        "POST",
        "https://trusted-gitea.internal/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={"client_secret": "secret"},
    )

    assert result == {"ok": True}
    pinned_fetch.assert_called_once_with(
        "POST",
        "https://trusted-gitea.internal/login/oauth/access_token",
        allowed_ips=[],
        allowed_hosts=["trusted-gitea.internal"],
        headers={"Accept": "application/json"},
        data={"client_secret": "secret"},
        timeout=10,
        stream=True,
    )
    response.close.assert_called_once_with()


@override_settings(GITEA_ALLOWED_IPS=[], GITEA_ALLOWED_HOSTS=[])
def test_gitea_transport_rejects_redirects_and_oversized_responses(mocker):
    redirect = MagicMock(status_code=302)
    mocker.patch(
        "plane.authentication.provider.oauth.gitea.pinned_fetch",
        return_value=redirect,
    )
    with pytest.raises(requests.RequestException):
        GiteaOAuthProvider._request_json("GET", "https://gitea.example.com/api/v1/user")
    redirect.close.assert_called_once_with()

    oversized = MagicMock(status_code=200)
    oversized.iter_content.return_value = [b"x" * (GITEA_RESPONSE_MAX_BYTES + 1)]
    mocker.patch(
        "plane.authentication.provider.oauth.gitea.pinned_fetch",
        return_value=oversized,
    )
    with pytest.raises(requests.RequestException):
        GiteaOAuthProvider._request_json("GET", "https://gitea.example.com/api/v1/user")
    oversized.close.assert_called_once_with()
