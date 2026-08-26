# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock, patch

import pytest
import requests

from plane.authentication.adapter.base import Adapter
from plane.authentication.adapter.error import AuthenticationException
from plane.authentication.adapter.oauth import OauthAdapter
from plane.authentication.provider.oauth.github import GitHubOAuthProvider


@pytest.mark.unit
class TestAuthenticationLogHygiene:
    def test_invalid_email_is_not_logged(self):
        adapter = Adapter(request=Mock(), provider="credentials")
        adapter.logger = Mock()
        submitted_email = "private-user@example"

        with pytest.raises(AuthenticationException):
            adapter.sanitize_email(submitted_email)

        adapter.logger.warning.assert_called_once_with("Email validation failed")
        assert submitted_email not in str(adapter.logger.mock_calls)

    def test_oauth_access_token_is_not_logged_when_user_request_fails(self):
        adapter = OauthAdapter(
            request=Mock(),
            provider="github",
            client_id="client-id",
            scope="read:user",
            redirect_uri="https://example.com/callback",
            auth_url="https://example.com/authorize",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/user",
        )
        adapter.logger = Mock()
        access_token = "secret-oauth-access-token"
        adapter.token_data = {"access_token": access_token}

        with patch("plane.authentication.adapter.oauth.requests.get", side_effect=requests.RequestException):
            with pytest.raises(AuthenticationException):
                adapter.get_user_response()

        # The message now carries the failure's type and text so an operator can
        # tell an egress refusal from an unreachable provider. What must stay out
        # is the request itself, which is what this asserts.
        adapter.logger.warning.assert_called_once()
        assert access_token not in str(adapter.logger.mock_calls)
        assert (
            "User info request" in adapter.logger.warning.call_args.args[0] % adapter.logger.warning.call_args.args[1:]
        )

    def test_github_membership_failure_does_not_log_identity_or_configuration(self):
        provider = object.__new__(GitHubOAuthProvider)
        provider.organization_id = "example-org"
        provider.token_data = {"access_token": "secret-oauth-access-token"}
        provider.logger = Mock()
        provider.get_user_response = Mock(return_value={"login": "private-user"})
        provider.is_user_in_organization = Mock(return_value=False)

        with pytest.raises(AuthenticationException):
            provider.set_user_data()

        provider.logger.warning.assert_called_once_with("User is not in organization")
        logged_calls = str(provider.logger.mock_calls)
        assert "private-user" not in logged_calls
        assert "example-org" not in logged_calls
        assert "secret-oauth-access-token" not in logged_calls
