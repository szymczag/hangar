# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode

import jwt
import pytz
import requests

# Django imports
from django.core.cache import cache

# Module imports
from plane.authentication.adapter.oauth import OauthAdapter
from plane.authentication.adapter.error import AuthenticationException
from plane.license.utils.instance_value import get_configuration_value

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES

DISCOVERY_CACHE_TTL = 60 * 15
DISCOVERY_TIMEOUT = 10

# Asymmetric algorithms only. Symmetric (HS*) algorithms are rejected because
# the verification key would be the client secret, which lets anyone who ever
# saw a token response forge id_tokens; `none` is rejected by PyJWT when an
# explicit algorithm list is supplied.
ALLOWED_ID_TOKEN_ALGS = [
    "RS256",
    "RS384",
    "RS512",
    "ES256",
    "ES384",
    "ES512",
    "PS256",
    "PS384",
    "PS512",
]

# One PyJWKClient per jwks_uri, reused across requests so its internal JWKS
# cache is effective.
_jwk_clients = {}


def _get_jwk_client(jwks_uri):
    client = _jwk_clients.get(jwks_uri)
    if client is None:
        client = jwt.PyJWKClient(jwks_uri, timeout=DISCOVERY_TIMEOUT)
        _jwk_clients[jwks_uri] = client
    return client


class OIDCOAuthProvider(OauthAdapter):
    provider = "oidc"
    scope = "openid email profile"

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
            OIDC_ISSUER,
            OIDC_CLIENT_ID,
            OIDC_CLIENT_SECRET,
            OIDC_ALLOW_UNVERIFIED_EMAIL,
        ) = get_configuration_value(
            [
                {"key": "OIDC_ISSUER", "default": os.environ.get("OIDC_ISSUER")},
                {"key": "OIDC_CLIENT_ID", "default": os.environ.get("OIDC_CLIENT_ID")},
                {
                    "key": "OIDC_CLIENT_SECRET",
                    "default": os.environ.get("OIDC_CLIENT_SECRET"),
                },
                {
                    "key": "OIDC_ALLOW_UNVERIFIED_EMAIL",
                    "default": os.environ.get("OIDC_ALLOW_UNVERIFIED_EMAIL", "0"),
                },
            ]
        )

        if not (OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        if not (OIDC_ISSUER.startswith("https://") or OIDC_ISSUER.startswith("http://")):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        self.issuer = OIDC_ISSUER.rstrip("/")
        self.allow_unverified_email = OIDC_ALLOW_UNVERIFIED_EMAIL == "1"
        self.nonce = nonce
        self.code_verifier = code_verifier

        discovery = self.__get_discovery_document()

        callback_path = "spaces/oidc/callback/" if is_space else "oidc/callback/"
        redirect_uri = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}/auth/{callback_path}"

        url_params = {
            "client_id": OIDC_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.scope,
            "state": state,
        }
        # The initiate endpoints always supply nonce + PKCE; they are optional
        # here only so the callback endpoints can construct the provider
        # without generating fresh values.
        if nonce:
            url_params["nonce"] = nonce
        if code_challenge:
            url_params["code_challenge"] = code_challenge
            url_params["code_challenge_method"] = "S256"
        auth_url = f"{discovery['authorization_endpoint']}?{urlencode(url_params)}"

        super().__init__(
            request,
            self.provider,
            OIDC_CLIENT_ID,
            self.scope,
            redirect_uri,
            auth_url,
            discovery["token_endpoint"],
            discovery.get("userinfo_endpoint"),
            OIDC_CLIENT_SECRET,
            code,
            callback=callback,
        )
        self.jwks_uri = discovery.get("jwks_uri")

    def __get_discovery_document(self):
        cache_key = f"ext:oidc:discovery:{self.issuer}"
        discovery = cache.get(cache_key)
        if discovery:
            return discovery
        try:
            response = requests.get(
                f"{self.issuer}/.well-known/openid-configuration",
                timeout=DISCOVERY_TIMEOUT,
            )
            response.raise_for_status()
            discovery = response.json()
        except (requests.RequestException, ValueError):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )

        # The discovery document is authoritative for every endpoint we will
        # send credentials to, so its issuer must match the configured one
        # exactly (OpenID Connect Discovery 1.0 §4.3).
        if discovery.get("issuer", "").rstrip("/") != self.issuer:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )
        for required in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not discovery.get(required):
                raise AuthenticationException(
                    error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                    error_message="OIDC_PROVIDER_ERROR",
                )

        cache.set(cache_key, discovery, DISCOVERY_CACHE_TTL)
        return discovery

    def set_token_data(self):
        data = {
            "grant_type": "authorization_code",
            "code": self.code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.code_verifier:
            data["code_verifier"] = self.code_verifier
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
                "refresh_token_expired_at": None,
                "id_token": token_response.get("id_token", ""),
            }
        )

    def __validate_id_token(self, id_token):
        try:
            signing_key = _get_jwk_client(self.jwks_uri).get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                key=signing_key.key,
                algorithms=ALLOWED_ID_TOKEN_ALGS,
                audience=self.client_id,
                issuer=self.issuer,
                leeway=30,
                options={"require": ["exp", "iat", "aud", "iss", "sub"]},
            )
        except jwt.PyJWKClientError:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )
        except jwt.InvalidTokenError:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"],
                error_message="OIDC_TOKEN_VALIDATION_FAILED",
            )

        # Replay/injection protection: the nonce we generated at initiate time
        # must round-trip through the IdP (OpenID Connect Core 1.0 §3.1.3.7).
        if not self.nonce or claims.get("nonce") != self.nonce:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"],
                error_message="OIDC_TOKEN_VALIDATION_FAILED",
            )

        # With multiple audiences the authorized party must be this client
        # (OpenID Connect Core 1.0 §3.1.3.7 step 4/5).
        aud = claims.get("aud")
        if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != self.client_id:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"],
                error_message="OIDC_TOKEN_VALIDATION_FAILED",
            )

        return claims

    def set_user_data(self):
        id_token = self.token_data.get("id_token")
        if not id_token:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"],
                error_message="OIDC_TOKEN_VALIDATION_FAILED",
            )
        claims = self.__validate_id_token(id_token)

        email = claims.get("email")
        email_verified = claims.get("email_verified")
        if (not email or email_verified is None) and self.userinfo_url:
            # Some IdPs keep profile claims out of the id_token; the userinfo
            # endpoint is the fallback source.
            userinfo = self.get_user_response()
            if userinfo.get("sub") != claims.get("sub"):
                raise AuthenticationException(
                    error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"],
                    error_message="OIDC_TOKEN_VALIDATION_FAILED",
                )
            email = email or userinfo.get("email")
            if email_verified is None:
                email_verified = userinfo.get("email_verified")
            claims = {**userinfo, **{k: v for k, v in claims.items() if v is not None}}

        if not email:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )

        # Never trust an unverified email — an IdP that lets users free-type
        # their address would allow takeover of any existing account (same
        # class of issue as GHSA-7j95-vh8g-f365). Deployments whose IdP omits
        # the claim entirely can opt out via OIDC_ALLOW_UNVERIFIED_EMAIL.
        if email_verified is not True and not self.allow_unverified_email:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_UNVERIFIED_EMAIL"],
                error_message="OIDC_UNVERIFIED_EMAIL",
            )

        first_name = claims.get("given_name")
        last_name = claims.get("family_name")
        if not first_name:
            name = claims.get("name") or email.split("@")[0]
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = last_name or (parts[1] if len(parts) > 1 else "")

        super().set_user_data(
            {
                "email": email,
                "user": {
                    "provider_id": str(claims.get("sub")),
                    "email": email,
                    "avatar": claims.get("picture"),
                    "first_name": first_name,
                    "last_name": last_name or "",
                    "is_password_autoset": True,
                },
            }
        )
