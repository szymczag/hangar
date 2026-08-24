# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlsplit, urlunsplit
import pytz
import requests

from django.conf import settings

# Module imports
from plane.authentication.adapter.oauth import OauthAdapter
from plane.license.utils.instance_value import get_configuration_value
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)


GITEA_RESPONSE_MAX_BYTES = 256 * 1024
GITEA_REQUEST_TIMEOUT = 10


class GiteaOAuthProvider(OauthAdapter):
    provider = "gitea"
    scope = "openid email profile read:user"

    def __init__(self, request, code=None, state=None, callback=None, is_space=False):
        (GITEA_CLIENT_ID, GITEA_CLIENT_SECRET, GITEA_HOST) = get_configuration_value(
            [
                {
                    "key": "GITEA_CLIENT_ID",
                    "default": os.environ.get("GITEA_CLIENT_ID"),
                },
                {
                    "key": "GITEA_CLIENT_SECRET",
                    "default": os.environ.get("GITEA_CLIENT_SECRET"),
                },
                {
                    "key": "GITEA_HOST",
                    "default": os.environ.get("GITEA_HOST"),
                },
            ]
        )

        if not (GITEA_CLIENT_ID and GITEA_CLIENT_SECRET and GITEA_HOST):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITEA_NOT_CONFIGURED"],
                error_message="GITEA_NOT_CONFIGURED",
            )

        # Treat the configured value as a base URL, not as an arbitrary request
        # target. Credentials and endpoint-specific URL components must never
        # be smuggled through instance configuration.
        try:
            parsed = urlsplit(GITEA_HOST)
            allowed_schemes = {"https", "http"} if settings.DEBUG else {"https"}
            if (
                parsed.scheme not in allowed_schemes
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or "\\" in GITEA_HOST
                or any(ord(character) < 0x20 for character in GITEA_HOST)
            ):
                raise ValueError("Unsafe Gitea URL")
            port = parsed.port
            hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
            host_label = f"[{hostname}]" if ":" in hostname else hostname
            netloc = host_label if port is None else f"{host_label}:{port}"
            GITEA_HOST = urlunsplit(
                (
                    parsed.scheme,
                    netloc,
                    parsed.path.rstrip("/"),
                    "",
                    "",
                )
            )
        except (TypeError, UnicodeError, ValueError):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITEA_NOT_CONFIGURED"],
                error_message="GITEA_NOT_CONFIGURED",  # avoid leaking details to query params
            )

        # Set URLs based on the host
        self.token_url = f"{GITEA_HOST}/login/oauth/access_token"
        self.userinfo_url = f"{GITEA_HOST}/api/v1/user"

        client_id = GITEA_CLIENT_ID
        client_secret = GITEA_CLIENT_SECRET

        callback_path = "/auth/spaces/gitea/callback/" if is_space else "/auth/gitea/callback/"
        redirect_uri = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}{callback_path}"
        url_params = {
            "client_id": client_id,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        auth_url = f"{GITEA_HOST}/login/oauth/authorize?{urlencode(url_params)}"

        super().__init__(
            request,
            self.provider,
            client_id,
            self.scope,
            redirect_uri,
            auth_url,
            self.token_url,
            self.userinfo_url,
            client_secret,
            code,
            callback=callback,
        )

    # Gitea is commonly self-hosted on an internal network, so private
    # destinations are reachable when the operator names them. Responses are
    # capped tighter than the shared default: these endpoints return a small
    # token or user object.
    outbound_max_response_bytes = GITEA_RESPONSE_MAX_BYTES
    outbound_timeout = GITEA_REQUEST_TIMEOUT

    def outbound_allowlist(self):
        return settings.GITEA_ALLOWED_IPS, settings.GITEA_ALLOWED_HOSTS

    def set_token_data(self):
        data = {
            "code": self.code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"Accept": "application/json"}
        token_response = self.get_user_token(data=data, headers=headers)
        super().set_token_data(
            {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token", None),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response.get("expires_in"))
                    if token_response.get("expires_in")
                    else None
                ),
                "refresh_token_expired_at": (
                    datetime.fromtimestamp(token_response.get("refresh_token_expired_at"), tz=pytz.utc)
                    if token_response.get("refresh_token_expired_at")
                    else None
                ),
                "id_token": token_response.get("id_token", ""),
            }
        )

    def __get_email(self, headers):
        try:
            # Gitea may not provide email in user response, so fetch it separately
            emails_url = f"{self.userinfo_url}/emails"
            emails_response = self._request_json("GET", emails_url, headers=headers)

            if not emails_response:
                raise AuthenticationException(
                    error_code=AUTHENTICATION_ERROR_CODES["GITEA_OAUTH_PROVIDER_ERROR"],
                    error_message="GITEA_OAUTH_PROVIDER_ERROR: No emails found",
                )
            # Prefer primary+verified, then any verified. Never fall back to an unverified
            # email — an attacker with a self-hosted Gitea instance could assert any address
            # to take over an existing account (GHSA-7j95-vh8g-f365).
            email = next((e.get("email") for e in emails_response if e.get("primary") and e.get("verified")), None)
            if not email:
                email = next((e.get("email") for e in emails_response if e.get("verified")), None)
            if not email:
                raise AuthenticationException(
                    error_code=AUTHENTICATION_ERROR_CODES["OAUTH_PROVIDER_UNVERIFIED_EMAIL"],
                    error_message="OAUTH_PROVIDER_UNVERIFIED_EMAIL",
                )
            return email
        except requests.RequestException:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITEA_OAUTH_PROVIDER_ERROR"],
                error_message="GITEA_OAUTH_PROVIDER_ERROR: Exception occurred while fetching emails",
            )

    def set_user_data(self):
        user_info_response = self.get_user_response()
        headers = {
            "Authorization": f"Bearer {self.token_data.get('access_token')}",
            "Accept": "application/json",
        }

        # Always use __get_email() which enforces the verified-email requirement.
        # The user object's .email field carries no verification flag, so it cannot
        # be trusted directly (GHSA-7j95-vh8g-f365).
        email = self.__get_email(headers=headers)

        super().set_user_data(
            {
                "email": email,
                "user": {
                    "provider_id": str(user_info_response.get("id")),
                    "email": email,
                    "avatar": user_info_response.get("avatar_url"),
                    "first_name": user_info_response.get("full_name") or user_info_response.get("login"),
                    "last_name": "",  # Gitea doesn't provide separate first/last name
                    "is_password_autoset": True,
                },
            }
        )
