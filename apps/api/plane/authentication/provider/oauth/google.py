# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode

import jwt
import pytz

# Module imports
from plane.authentication.adapter.oauth import OauthAdapter
from plane.authentication.services import ExternalIdentity
from plane.license.utils.instance_value import get_configuration_value
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ID_TOKEN_ALGORITHMS = ["RS256"]
_google_jwk_client = None


def _get_google_jwk_client():
    global _google_jwk_client
    if _google_jwk_client is None:
        _google_jwk_client = jwt.PyJWKClient(GOOGLE_JWKS_URL)
    return _google_jwk_client


class GoogleOAuthProvider(OauthAdapter):
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    scope = "openid email profile"
    provider = "google"

    def __init__(
        self,
        request,
        code=None,
        state=None,
        callback=None,
        nonce=None,
        code_verifier=None,
        code_challenge=None,
        is_space=False,
    ):
        (
            IS_GOOGLE_ENABLED,
            GOOGLE_CLIENT_ID,
            GOOGLE_CLIENT_SECRET,
            GOOGLE_AUTH_MODE,
            GOOGLE_WORKSPACE_DOMAINS,
        ) = get_configuration_value(
            [
                {
                    "key": "IS_GOOGLE_ENABLED",
                    "default": os.environ.get("IS_GOOGLE_ENABLED", "0"),
                },
                {
                    "key": "GOOGLE_CLIENT_ID",
                    "default": os.environ.get("GOOGLE_CLIENT_ID"),
                },
                {
                    "key": "GOOGLE_CLIENT_SECRET",
                    "default": os.environ.get("GOOGLE_CLIENT_SECRET"),
                },
                {
                    "key": "GOOGLE_AUTH_MODE",
                    "default": os.environ.get("GOOGLE_AUTH_MODE", "generic"),
                },
                {
                    "key": "GOOGLE_WORKSPACE_DOMAINS",
                    "default": os.environ.get("GOOGLE_WORKSPACE_DOMAINS", ""),
                },
            ]
        )

        auth_mode = str(GOOGLE_AUTH_MODE or "generic").strip().lower()
        try:
            workspace_domains = {
                domain.strip().encode("idna").decode("ascii").lower()
                for domain in str(GOOGLE_WORKSPACE_DOMAINS or "").split(",")
                if domain.strip()
            }
        except UnicodeError:
            workspace_domains = set()
        if (
            IS_GOOGLE_ENABLED != "1"
            or not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
            or auth_mode not in {"generic", "workspace"}
            or (auth_mode == "workspace" and not workspace_domains)
        ):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_NOT_CONFIGURED"],
                error_message="GOOGLE_NOT_CONFIGURED",
            )

        client_id = GOOGLE_CLIENT_ID
        client_secret = GOOGLE_CLIENT_SECRET
        self.nonce = nonce
        self.code_verifier = code_verifier
        self.auth_mode = auth_mode
        self.workspace_domains = workspace_domains

        callback_path = "spaces/google/callback/" if is_space else "google/callback/"
        redirect_uri = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}/auth/{callback_path}"
        url_params = {
            "client_id": client_id,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if nonce:
            url_params["nonce"] = nonce
        if code_challenge:
            url_params["code_challenge"] = code_challenge
            url_params["code_challenge_method"] = "S256"
        if auth_mode == "workspace" and len(workspace_domains) == 1:
            url_params["hd"] = next(iter(workspace_domains))
        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(url_params)}"

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

    def set_token_data(self):
        data = {
            "code": self.code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        if self.code_verifier:
            data["code_verifier"] = self.code_verifier
        token_response = self.get_user_token(data=data)
        access_token = token_response.get("access_token")
        id_token = token_response.get("id_token")
        if not isinstance(access_token, str) or not access_token or not isinstance(id_token, str) or not id_token:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )
        expires_in = token_response.get("expires_in")
        try:
            expires_in = float(expires_in) if expires_in is not None else None
            if expires_in is not None and expires_in <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )
        super().set_token_data(
            {
                "access_token": access_token,
                "refresh_token": token_response.get("refresh_token", None),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=expires_in) if expires_in is not None else None
                ),
                "refresh_token_expired_at": (
                    datetime.fromtimestamp(token_response.get("refresh_token_expired_at"), tz=pytz.utc)
                    if token_response.get("refresh_token_expired_at")
                    else None
                ),
                "id_token": id_token,
            }
        )

    def _validate_id_token(self):
        try:
            id_token = self.token_data.get("id_token")
            signing_key = _get_google_jwk_client().get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                key=signing_key.key,
                algorithms=GOOGLE_ID_TOKEN_ALGORITHMS,
                audience=self.client_id,
                leeway=30,
                options={"require": ["exp", "iat", "aud", "iss", "sub", "nonce", "email", "email_verified"]},
            )
        except (jwt.InvalidTokenError, jwt.PyJWKClientError, ValueError, TypeError):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )

        if claims.get("iss") not in GOOGLE_ISSUERS or not self.nonce or claims.get("nonce") != self.nonce:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )
        audiences = claims.get("aud")
        authorized_party = claims.get("azp")
        if (isinstance(audiences, list) and len(audiences) > 1 and authorized_party is None) or (
            authorized_party is not None and authorized_party != self.client_id
        ):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )
        if claims.get("email_verified") is not True:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OAUTH_PROVIDER_UNVERIFIED_EMAIL"],
                error_message="OAUTH_PROVIDER_UNVERIFIED_EMAIL",
            )
        if self.auth_mode == "workspace":
            hosted_domain = claims.get("hd")
            try:
                hosted_domain = hosted_domain.encode("idna").decode("ascii").lower() if hosted_domain else ""
            except UnicodeError:
                hosted_domain = ""
            if hosted_domain not in self.workspace_domains:
                raise AuthenticationException(
                    error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_WORKSPACE_TENANT_NOT_ALLOWED"],
                    error_message="GOOGLE_WORKSPACE_TENANT_NOT_ALLOWED",
                )
        return claims

    def set_user_data(self):
        claims = self._validate_id_token()
        user_info_response = self.get_user_response()
        if user_info_response.get("id") != claims.get("sub") or self.sanitize_email(
            user_info_response.get("email")
        ) != self.sanitize_email(claims.get("email")):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )
        canonical_issuer = "https://accounts.google.com"
        email = claims.get("email")
        subject = str(claims.get("sub"))
        user_data = {
            "email": email,
            "user": {
                "avatar": user_info_response.get("picture"),
                "first_name": user_info_response.get("given_name") or claims.get("given_name"),
                "last_name": user_info_response.get("family_name") or claims.get("family_name"),
                "provider_id": subject,
                "is_password_autoset": True,
            },
        }
        super().set_user_data(user_data)
        self.set_external_identity(
            ExternalIdentity(
                provider=self.provider,
                issuer=canonical_issuer,
                subject=subject,
                subject_format="",
                email=email,
                email_verified=True,
                first_name=user_data["user"]["first_name"] or "",
                last_name=user_data["user"]["last_name"] or "",
                avatar_url=user_data["user"]["avatar"] or "",
                metadata={"hosted_domain": claims.get("hd", "")},
                legacy_provider_account_id=subject,
            )
        )
