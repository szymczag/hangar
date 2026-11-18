# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""OAuth callbacks proceed only on a matching, unexpired, single-use transaction.

Hangar keeps the pending OAuth state in a per-provider session transaction
(``plane.authentication.utils.oauth_transaction``; Google keeps its own with the
PKCE verifier and nonce). The callback pops the transaction before comparing, so
any callback, matching or not, spends it.
"""

import time
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from django.test import Client
from django.urls import reverse

from plane.authentication.utils.oauth_transaction import OAUTH_TRANSACTION_TTL
from plane.authentication.views.app.gitea import GITEA_TRANSACTION_APP
from plane.authentication.views.app.github import GITHUB_TRANSACTION_APP
from plane.authentication.views.app.gitlab import GITLAB_TRANSACTION_APP
from plane.authentication.views.app.google import GOOGLE_TRANSACTION_APP
from plane.authentication.views.space.gitea import GITEA_TRANSACTION_SPACE

CALLBACKS = [
    ("github-callback", "plane.authentication.views.app.github.GitHubOAuthProvider", GITHUB_TRANSACTION_APP),
    ("gitlab-callback", "plane.authentication.views.app.gitlab.GitLabOAuthProvider", GITLAB_TRANSACTION_APP),
    ("google-callback", "plane.authentication.views.app.google.GoogleOAuthProvider", GOOGLE_TRANSACTION_APP),
    ("gitea-callback", "plane.authentication.views.app.gitea.GiteaOAuthProvider", GITEA_TRANSACTION_APP),
    ("space-gitea-callback", "plane.authentication.views.space.gitea.GiteaOAuthProvider", GITEA_TRANSACTION_SPACE),
]


def _client(transaction_key, session_state=None, created_at=None):
    client = Client()
    session = client.session
    if session_state is not None:
        session[transaction_key] = {
            "state": session_state,
            "host": "http://localhost",
            "next_path": None,
            "created_at": time.time() if created_at is None else created_at,
            # Google's transaction also carries its PKCE verifier and nonce.
            "code_verifier": "code-verifier",
            "nonce": "nonce",
        }
    session.save()
    return client


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url_name,provider_path,transaction_key", CALLBACKS, ids=[c[0] for c in CALLBACKS])
class TestOAuthCallbackState:
    """The OAuth callback proceeds only when the state matches the pending transaction."""

    @pytest.mark.parametrize("state_param", [None, ""], ids=["no-state-param", "empty-state-param"])
    def test_refused_without_session_state(self, url_name, provider_path, transaction_key, state_param):
        params = {"code": "oauth-code"}
        if state_param is not None:
            params["state"] = state_param
        client = _client(transaction_key)

        with patch(provider_path) as provider:
            response = client.get(reverse(url_name), params)

        assert response.status_code == 302
        assert "error_code" in response.url
        provider.assert_not_called()
        assert "_auth_user_id" not in client.session

    def test_refused_on_mismatched_state(self, url_name, provider_path, transaction_key):
        client = _client(transaction_key, session_state="expected-state")

        with patch(provider_path) as provider:
            response = client.get(reverse(url_name), {"code": "oauth-code", "state": "other-state"})

        assert response.status_code == 302
        assert "error_code" in response.url
        provider.assert_not_called()
        assert "_auth_user_id" not in client.session

    def test_mismatched_state_spends_pending_transaction(self, url_name, provider_path, transaction_key, create_user):
        """Hangar is stricter than upstream here: a forged callback also spends the
        pending transaction, so the genuine state is refused afterwards."""
        client = _client(transaction_key, session_state="expected-state")

        with patch(provider_path) as provider:
            response = client.get(reverse(url_name), {"code": "oauth-code", "state": "other-state"})

        assert "error_code" in response.url
        provider.assert_not_called()
        assert transaction_key not in client.session

        with patch(provider_path) as provider:
            provider.return_value.authenticate.return_value = create_user
            response = client.get(reverse(url_name), {"code": "oauth-code", "state": "expected-state"})

        assert "error_code" in response.url
        provider.assert_not_called()
        assert "_auth_user_id" not in client.session

    def test_refused_on_expired_transaction(self, url_name, provider_path, transaction_key):
        client = _client(
            transaction_key,
            session_state="expected-state",
            created_at=time.time() - OAUTH_TRANSACTION_TTL - 1,
        )

        with patch(provider_path) as provider:
            response = client.get(reverse(url_name), {"code": "oauth-code", "state": "expected-state"})

        assert response.status_code == 302
        assert "error_code" in response.url
        provider.assert_not_called()
        assert "_auth_user_id" not in client.session

    def test_matching_state_logs_in_once(self, url_name, provider_path, transaction_key, create_user):
        client = _client(transaction_key, session_state="expected-state")
        params = {"code": "oauth-code", "state": "expected-state"}

        with patch(provider_path) as provider:
            provider.return_value.authenticate.return_value = create_user
            response = client.get(reverse(url_name), params)

        assert response.status_code == 302
        assert "error_code" not in response.url
        assert provider.call_args.kwargs["code"] == "oauth-code"
        assert client.session["_auth_user_id"] == str(create_user.id)
        assert transaction_key not in client.session

        # The stored transaction is single-use.
        with patch(provider_path) as provider:
            response = client.get(reverse(url_name), params)

        assert "error_code" in response.url
        provider.assert_not_called()


APP_CALLBACKS = ["github-callback", "gitlab-callback", "google-callback", "gitea-callback"]


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url_name", APP_CALLBACKS)
def test_refused_without_session_redirects_to_app_host(url_name, settings):
    settings.APP_BASE_URL = "http://app.example.com"

    response = Client().get(reverse(url_name), {"code": "oauth-code", "state": "some-state"})

    assert response.status_code == 302
    location = urlparse(response.url)
    assert (location.scheme, location.netloc) == ("http", "app.example.com")
    assert "error_code" in response.url
