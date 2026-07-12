# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import time
from socket import getaddrinfo as _getaddrinfo
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import jwt
import pytz
import requests

# Django imports
from django.core.cache import cache
from django.conf import settings

# Module imports
from plane.authentication.adapter.oauth import OauthAdapter
from plane.authentication.adapter.error import AuthenticationException
from plane.license.utils.instance_value import get_configuration_value

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES

DISCOVERY_CACHE_TTL = 60 * 15
DISCOVERY_TIMEOUT = 10
MAX_RESOLVED_ADDRESSES = 8

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

# Reuse the validated transport wrapper, but fetch and validate JWKS on every
# signature check so cached key material cannot bypass the destination policy.
_jwk_clients = {}


@dataclass(frozen=True)
class ResolvedAddress:
    family: int
    socktype: int
    protocol: int
    sockaddr: tuple
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass(frozen=True)
class ResolvedOIDCTarget:
    url: str
    parsed: object
    scheme: str
    hostname: str
    port: int
    origin: tuple[str, str, int]
    addresses: tuple[ResolvedAddress, ...]


class OIDCResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"OIDC provider returned HTTP {self.status_code}")

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def _normalize_hostname(hostname):
    if "%" in hostname:
        raise ValueError("Scoped IPv6 addresses are not allowed")
    return hostname.encode("idna").decode("ascii").lower()


def _normalize_ip(address):
    parsed = ipaddress.ip_address(address.split("%", 1)[0])
    return parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped else parsed


def _url_origin(parsed):
    default_port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, _normalize_hostname(parsed.hostname), parsed.port or default_port


def validate_outbound_url(url, *, required_origin=None):
    """Resolve and validate the exact socket addresses an OIDC request may use."""
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme not in ({"https", "http"} if settings.DEBUG else {"https"})
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("Unsafe OIDC URL")
        if parsed.scheme == "http" and not settings.DEBUG:
            raise ValueError("OIDC HTTP is only allowed in development")
        origin = _url_origin(parsed)
        if required_origin is not None and origin != required_origin:
            raise ValueError("OIDC endpoint origin does not match issuer")

        hostname = origin[1]
        port = origin[2]
        answers = _getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not answers:
            raise ValueError("OIDC hostname did not resolve")
        resolved = []
        seen = set()
        for family, socktype, protocol, _, sockaddr in answers:
            if family not in (socket.AF_INET, socket.AF_INET6) or socktype != socket.SOCK_STREAM:
                raise ValueError("OIDC hostname returned an unsupported address")
            if sockaddr[1] != port:
                raise ValueError("OIDC resolver returned an unexpected port")
            address = _normalize_ip(sockaddr[0])
            if not address.is_global:
                raise ValueError("OIDC hostname resolves to a non-public address")
            key = (family, sockaddr)
            if key not in seen:
                seen.add(key)
                resolved.append(ResolvedAddress(family, socktype, protocol, sockaddr, address))
        if len(resolved) > MAX_RESOLVED_ADDRESSES:
            raise ValueError("OIDC hostname returned too many addresses")
    except (OSError, ValueError) as exc:
        raise ValueError("Unsafe OIDC URL") from exc
    return ResolvedOIDCTarget(url, parsed, parsed.scheme, hostname, port, origin, tuple(resolved))


def _checked_response(response):
    if 300 <= response.status_code < 400:
        raise requests.RequestException("OIDC redirects are not allowed")
    response.raise_for_status()
    return response


def _connect_pinned(target, address, timeout):
    raw_socket = socket.socket(address.family, address.socktype, address.protocol)
    raw_socket.settimeout(timeout)
    try:
        raw_socket.connect(address.sockaddr)
        peer_ip = _normalize_ip(raw_socket.getpeername()[0])
        if peer_ip != address.ip:
            raise OSError("OIDC connection peer does not match the validated address")
        if target.scheme == "https":
            raw_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=target.hostname)
        return raw_socket
    except Exception:
        raw_socket.close()
        raise


def _request_oidc(method, target, *, data=None, headers=None, timeout=DISCOVERY_TIMEOUT):
    body = None
    request_headers = {"Accept": "application/json", "Connection": "close", **(headers or {})}
    if data is not None:
        body = urlencode(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    path = urlunparse(("", "", target.parsed.path or "/", target.parsed.params, target.parsed.query, ""))
    last_error = None
    deadline = time.monotonic() + timeout
    for address in target.addresses:
        connection = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            connection_class = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
            connection = connection_class(target.hostname, target.port, timeout=remaining)
            connection.sock = _connect_pinned(target, address, remaining)
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            result = OIDCResponse(response.status, response.read())
            return _checked_response(result)
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            if connection is not None:
                connection.close()
    raise requests.ConnectionError("Unable to connect to the validated OIDC destination") from last_error


class _ValidatedJWKClient:
    def __init__(self, jwks_uri, issuer_origin):
        self.jwks_uri = jwks_uri
        self.issuer_origin = issuer_origin

    def get_signing_key_from_jwt(self, token):
        target = validate_outbound_url(self.jwks_uri, required_origin=self.issuer_origin)
        response = _request_oidc("GET", target)
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise jwt.PyJWKClientError("Invalid JWKS response")
        kid = jwt.get_unverified_header(token).get("kid")
        candidates = [key for key in payload["keys"] if kid is None or key.get("kid") == kid]
        if len(candidates) != 1:
            raise jwt.PyJWKClientError("Unable to select a signing key")
        return jwt.PyJWK.from_dict(candidates[0])


def _get_jwk_client(jwks_uri, issuer_origin=None):
    cache_key = (jwks_uri, issuer_origin)
    client = _jwk_clients.get(cache_key)
    if client is None:
        client = _ValidatedJWKClient(jwks_uri, issuer_origin)
        _jwk_clients[cache_key] = client
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
            IS_OIDC_ENABLED,
            OIDC_ISSUER,
            OIDC_CLIENT_ID,
            OIDC_CLIENT_SECRET,
            OIDC_ALLOW_UNVERIFIED_EMAIL,
        ) = get_configuration_value(
            [
                {
                    "key": "IS_OIDC_ENABLED",
                    "default": os.environ.get("IS_OIDC_ENABLED", "0"),
                },
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

        if IS_OIDC_ENABLED != "1" or not (OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        try:
            issuer_target = validate_outbound_url(OIDC_ISSUER)
            if issuer_target.parsed.query:
                raise ValueError("Issuer URLs cannot contain a query")
        except ValueError:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        self.issuer = OIDC_ISSUER.rstrip("/")
        self.issuer_origin = issuer_target.origin
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
        authorization_url = urlparse(discovery["authorization_endpoint"])
        reserved_params = set(url_params)
        existing_params = [
            (key, value)
            for key, value in parse_qsl(authorization_url.query, keep_blank_values=True)
            if key not in reserved_params
        ]
        auth_url = urlunparse(authorization_url._replace(query=urlencode([*existing_params, *url_params.items()])))

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

    def get_user_token(self, data, headers=None):
        try:
            target = validate_outbound_url(self.get_token_url(), required_origin=self.issuer_origin)
            response = _request_oidc("POST", target, data=data, headers=headers or {})
            token_response = response.json()
            if not isinstance(token_response, dict):
                raise ValueError("OIDC token response is not an object")
            return token_response
        except (requests.RequestException, ValueError):
            self.logger.warning("OIDC token request failed")
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )

    def get_user_response(self):
        try:
            target = validate_outbound_url(self.get_user_info_url(), required_origin=self.issuer_origin)
            response = _request_oidc(
                "GET",
                target,
                headers={"Authorization": f"Bearer {self.token_data.get('access_token')}"},
            )
            userinfo = response.json()
            if not isinstance(userinfo, dict):
                raise ValueError("OIDC userinfo response is not an object")
            return userinfo
        except (requests.RequestException, ValueError):
            self.logger.warning("OIDC userinfo request failed")
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )

    def __get_discovery_document(self):
        cache_key = f"ext:oidc:discovery:{self.issuer}"
        discovery = cache.get(cache_key)
        if not discovery:
            try:
                discovery_url = f"{self.issuer}/.well-known/openid-configuration"
                target = validate_outbound_url(discovery_url, required_origin=self.issuer_origin)
                response = _request_oidc("GET", target)
                discovery = response.json()
                if not isinstance(discovery, dict):
                    raise ValueError("OIDC discovery response is not an object")
            except (requests.RequestException, ValueError):
                raise AuthenticationException(
                    error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                    error_message="OIDC_PROVIDER_ERROR",
                )

        # Validate cached documents too. Besides being defensive against cache
        # corruption, this keeps validation effective after security rules are
        # tightened while an older document is still cached.
        if not isinstance(discovery, dict):
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
        for endpoint_name in (
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
            "userinfo_endpoint",
        ):
            endpoint = discovery.get(endpoint_name)
            if endpoint_name != "userinfo_endpoint" and not endpoint:
                raise AuthenticationException(
                    error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                    error_message="OIDC_PROVIDER_ERROR",
                )
            if not endpoint:
                continue
            try:
                validate_outbound_url(
                    endpoint,
                    required_origin=None if endpoint_name == "authorization_endpoint" else self.issuer_origin,
                )
            except ValueError:
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
        access_token = token_response.get("access_token")
        id_token = token_response.get("id_token")
        if not isinstance(access_token, str) or not access_token or not isinstance(id_token, str) or not id_token:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )
        expires_in = token_response.get("expires_in")
        try:
            expires_in = float(expires_in) if expires_in is not None else None
            if expires_in is not None and expires_in <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )
        super().set_token_data(
            {
                "access_token": access_token,
                "refresh_token": token_response.get("refresh_token", None),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=expires_in) if expires_in is not None else None
                ),
                "refresh_token_expired_at": None,
                "id_token": id_token,
            }
        )

    def __validate_id_token(self, id_token):
        try:
            signing_key = _get_jwk_client(self.jwks_uri, self.issuer_origin).get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                key=signing_key.key,
                algorithms=ALLOWED_ID_TOKEN_ALGS,
                audience=self.client_id,
                issuer=self.issuer,
                leeway=30,
                options={"require": ["exp", "iat", "aud", "iss", "sub"]},
            )
        except (jwt.PyJWKClientError, requests.RequestException, ValueError):
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

        # With multiple audiences an authorized party is required, and whenever
        # azp is present it must identify this client (OIDC Core §3.1.3.7).
        aud = claims.get("aud")
        azp = claims.get("azp")
        if (isinstance(aud, list) and len(aud) > 1 and azp is None) or (azp is not None and azp != self.client_id):
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
                    # `sub` is unique only within an issuer. Hash the pair into
                    # Account.provider_account_id so changing providers cannot
                    # collide with an account from a previous issuer.
                    "provider_id": hashlib.sha256(f"{self.issuer}\0{claims.get('sub')}".encode()).hexdigest(),
                    "email": email,
                    "avatar": claims.get("picture"),
                    "first_name": first_name,
                    "last_name": last_name or "",
                    "is_password_autoset": True,
                },
            }
        )
