# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import requests

# Django imports
from django.utils import timezone

from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)

# Module imports
from plane.authentication.utils.outbound import TLSPolicy, fetch_validated
from plane.db.models import Account
from .base import Adapter


class OauthAdapter(Adapter):
    # Every OAuth destination goes through the validated transport: resolved
    # once, pinned to a checked address, redirects refused, body capped, and a
    # deadline on every request. TLS 1.2 is the floor rather than 1.3 because
    # self-managed GitLab and Gitea hosts are legitimate destinations here.
    outbound_tls_policy = TLSPolicy.MIN_TLS12
    outbound_timeout = 10
    outbound_max_response_bytes = 1024 * 1024

    def outbound_required_origin(self):
        """Origin that derived endpoints must belong to, or None.

        Providers whose host is operator-supplied override this so a token or
        userinfo URL cannot address a different host than the one configured.
        """
        return None

    def outbound_allowlist(self):
        """(allowed_ips, allowed_hosts) for reaching an internal provider.

        Only self-hosted providers override this. Public-only is the default.
        """
        return None, None

    def __init__(
        self,
        request,
        provider,
        client_id,
        scope,
        redirect_uri,
        auth_url,
        token_url,
        userinfo_url,
        client_secret=None,
        code=None,
        callback=None,
    ):
        super().__init__(request=request, provider=provider, callback=callback)
        self.client_id = client_id
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.auth_url = auth_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.client_secret = client_secret
        self.code = code

    def authentication_error_code(self):
        if self.provider == "google":
            return "GOOGLE_OAUTH_PROVIDER_ERROR"
        elif self.provider == "github":
            return "GITHUB_OAUTH_PROVIDER_ERROR"
        elif self.provider == "gitlab":
            return "GITLAB_OAUTH_PROVIDER_ERROR"
        elif self.provider == "gitea":
            return "GITEA_OAUTH_PROVIDER_ERROR"
        else:
            return "OAUTH_NOT_CONFIGURED"

    def get_auth_url(self):
        return self.auth_url

    def get_token_url(self):
        return self.token_url

    def get_user_info_url(self):
        return self.userinfo_url

    def authenticate(self):
        self.set_token_data()
        self.set_user_data()
        return self.complete_login_or_signup()

    def fetch(self, method, url, *, data=None, headers=None):
        """Perform one validated request against a provider endpoint."""
        allowed_ips, allowed_hosts = self.outbound_allowlist()
        return fetch_validated(
            method,
            url,
            required_origin=self.outbound_required_origin(),
            allowed_ips=allowed_ips,
            allowed_hosts=allowed_hosts,
            data=data,
            headers=headers,
            timeout=self.outbound_timeout,
            max_response_bytes=self.outbound_max_response_bytes,
            tls_policy=self.outbound_tls_policy,
        )

    def get_user_token(self, data, headers=None):
        try:
            response = self.fetch("POST", self.get_token_url(), data=data, headers=headers or {})
            return response.json()
        except (requests.RequestException, ValueError):
            self.logger.warning("Error getting user token")
            code = self.authentication_error_code()
            raise AuthenticationException(error_code=AUTHENTICATION_ERROR_CODES[code], error_message=str(code))

    def get_user_response(self):
        try:
            response = self.fetch(
                "GET",
                self.get_user_info_url(),
                headers={"Authorization": f"Bearer {self.token_data.get('access_token')}"},
            )
            return response.json()
        except (requests.RequestException, ValueError):
            # Do not log headers here: they carry the access token
            self.logger.warning("Error getting user response")
            code = self.authentication_error_code()
            raise AuthenticationException(error_code=AUTHENTICATION_ERROR_CODES[code], error_message=str(code))

    def create_update_account(self, user, identity=None):
        provider_account_id = self.user_data.get("user", {}).get("provider_id")
        accounts = Account.objects.select_for_update() if identity is not None else Account.objects
        account = accounts.filter(
            provider=self.provider,
            provider_account_id=provider_account_id,
        ).first()
        if account and account.user_id != user.id:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["FEDERATED_IDENTITY_CONFLICT"],
                error_message="FEDERATED_IDENTITY_CONFLICT",
            )
        if account:
            account.access_token = self.token_data.get("access_token")
            account.refresh_token = self.token_data.get("refresh_token", None)
            account.access_token_expired_at = self.token_data.get("access_token_expired_at")
            account.refresh_token_expired_at = self.token_data.get("refresh_token_expired_at")
            account.last_connected_at = timezone.now()
            account.id_token = self.token_data.get("id_token", "")
            if identity is not None:
                account.identity = identity
            account.save()
        else:
            Account.objects.create(
                user=user,
                identity=identity,
                provider=self.provider,
                provider_account_id=provider_account_id,
                access_token=self.token_data.get("access_token"),
                refresh_token=self.token_data.get("refresh_token", None),
                access_token_expired_at=self.token_data.get("access_token_expired_at"),
                refresh_token_expired_at=self.token_data.get("refresh_token_expired_at"),
                last_connected_at=timezone.now(),
                id_token=self.token_data.get("id_token", ""),
            )
