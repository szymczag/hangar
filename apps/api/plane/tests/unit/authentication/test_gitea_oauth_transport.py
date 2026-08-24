# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
from django.test import override_settings

from plane.authentication.adapter.error import AuthenticationException
from plane.authentication.utils.outbound import TLSPolicy
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


@override_settings(GITEA_ALLOWED_IPS=[], GITEA_ALLOWED_HOSTS=["trusted-gitea.internal"])
def test_gitea_sends_its_allowlist_and_caps_through_the_shared_transport(mocker):
    """Gitea no longer carries its own transport; it configures the shared one.

    The operator allowlist is what makes an internal Gitea reachable at all,
    so losing it here would silently break self-hosted deployments.
    """
    provider = _provider(mocker, "https://trusted-gitea.internal")
    fetch = mocker.patch(
        "plane.authentication.adapter.oauth.fetch_validated",
        return_value=SimpleNamespace(json=lambda: {"ok": True}),
    )

    result = provider.get_user_token({"client_secret": "secret"}, headers={"Accept": "application/json"})

    assert result == {"ok": True}
    kwargs = fetch.call_args.kwargs
    assert kwargs["allowed_hosts"] == ["trusted-gitea.internal"]
    assert kwargs["allowed_ips"] == []
    assert kwargs["max_response_bytes"] == GITEA_RESPONSE_MAX_BYTES
    assert kwargs["tls_policy"] == TLSPolicy.MIN_TLS12


@override_settings(GITEA_ALLOWED_IPS=[], GITEA_ALLOWED_HOSTS=[])
def test_gitea_transport_failures_surface_as_provider_errors(mocker):
    mocker.patch(
        "plane.authentication.adapter.oauth.fetch_validated",
        side_effect=requests.RequestException("Outbound redirects are not allowed"),
    )
    provider = _provider(mocker, "https://gitea.example.com")

    with pytest.raises(AuthenticationException):
        provider.get_user_token({"client_secret": "secret"})
