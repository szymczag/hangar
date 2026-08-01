# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import ssl
import time
import uuid
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.test import Client
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from plane.db.models import Account, User
from plane.license.models import Instance, InstanceConfiguration

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES
from plane.ext.auth.provider.oidc import OIDCResponse, _checked_response, _connect_pinned, validate_outbound_url
from plane.ext.auth.views.oidc import SESSION_NONCE, SESSION_STATE, SESSION_VERIFIER
from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES

ISSUER = "https://idp.test"
CLIENT_ID = "hangar-client"
DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/authorize",
    "token_endpoint": f"{ISSUER}/token",
    "userinfo_endpoint": f"{ISSUER}/userinfo",
    "jwks_uri": f"{ISSUER}/jwks",
}


# One signing key for the whole module — generating RSA keys per test is slow.
_RSA_KEY = None


def get_rsa_key():
    global _RSA_KEY
    if _RSA_KEY is None:
        _RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return _RSA_KEY


@pytest.fixture
def setup_instance(db):
    instance_id = uuid.uuid4() if not Instance.objects.exists() else Instance.objects.first().id
    instance, _ = Instance.objects.update_or_create(
        id=instance_id,
        defaults={
            "instance_name": "Test Instance",
            "instance_id": str(uuid.uuid4()),
            "current_version": "1.0.0",
            "domain": "http://localhost:8000",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )
    return instance


@pytest.fixture
def oidc_config(db):
    """Configure the OIDC provider and pre-seed the discovery cache."""
    for key, value in (
        ("IS_OIDC_ENABLED", "1"),
        ("OIDC_ISSUER", ISSUER),
        ("OIDC_CLIENT_ID", CLIENT_ID),
        ("OIDC_CLIENT_SECRET", "test-secret"),
        ("ENABLE_SIGNUP", "1"),
    ):
        InstanceConfiguration.objects.update_or_create(
            key=key, defaults={"value": value, "category": "OIDC", "is_encrypted": False}
        )
    cache.set(f"ext:oidc:discovery:{ISSUER}", DISCOVERY, 60)
    yield
    cache.delete(f"ext:oidc:discovery:{ISSUER}")


@pytest.fixture
def django_client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) test-client")


@pytest.fixture(autouse=True)
def public_oidc_dns(mocker):
    """OIDC contracts are deterministic and never perform real DNS lookups."""
    return mocker.patch(
        "plane.ext.auth.provider.oidc._getaddrinfo",
        return_value=[(2, 1, 6, "", ("8.8.8.8", 443))],
    )


def make_id_token(rsa_key, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "user-123",
        "iat": now,
        "exp": now + 300,
        "email": "oidc-user@hangar.test",
        "email_verified": True,
        "given_name": "Otto",
        "family_name": "Idconnect",
        "nonce": "placeholder",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, rsa_key, algorithm="RS256")


def initiate(django_client):
    """Run the initiate step and return the session's state/nonce."""
    response = django_client.get(reverse("oidc-initiate"))
    assert response.status_code == 302
    return (
        django_client.session[SESSION_STATE],
        django_client.session[SESSION_NONCE],
        response,
    )


def run_callback(
    django_client,
    rsa_key,
    token_overrides=None,
    token_response_overrides=None,
    state=None,
    code="auth-code",
    userinfo_response=None,
):
    """Drive the callback with a canned token response signed by rsa_key."""
    session_state, nonce, _ = initiate(django_client)
    overrides = {"nonce": nonce}
    overrides.update(token_overrides or {})
    id_token = make_id_token(rsa_key, **overrides)
    token_response = {"access_token": "at-123", "expires_in": 3600, "id_token": id_token}
    token_response.update(token_response_overrides or {})

    fake_jwk_client = SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=rsa_key.public_key()))
    with (
        patch(
            "plane.ext.auth.provider.oidc.OIDCOAuthProvider.get_user_token",
            return_value=token_response,
        ),
        patch("plane.ext.auth.provider.oidc._get_jwk_client", return_value=fake_jwk_client),
    ):
        params = {"code": code, "state": state if state is not None else session_state}
        if userinfo_response is not None:
            with patch(
                "plane.ext.auth.provider.oidc.OIDCOAuthProvider.get_user_response",
                return_value=userinfo_response,
            ):
                return django_client.get(reverse("oidc-callback"), params)
        return django_client.get(reverse("oidc-callback"), params)


def error_code_of(response):
    query = parse_qs(urlparse(response["Location"]).query)
    return int(query["error_code"][0]) if "error_code" in query else None


@pytest.mark.contract
class TestOIDCOutboundURLPolicy:
    @pytest.mark.parametrize(
        "url,address",
        [
            ("https://localhost/oidc", "127.0.0.1"),
            ("https://private.test/oidc", "10.0.0.1"),
            ("https://link-local.test/oidc", "169.254.169.254"),
            ("https://reserved.test/oidc", "192.0.2.1"),
            ("https://ipv6-private.test/oidc", "fd00::1"),
            ("https://nat64-loopback.test/oidc", "64:ff9b::7f00:1"),
            ("https://nat64-metadata.test/oidc", "64:ff9b::a9fe:a9fe"),
            ("https://nat64-local-use.test/oidc", "64:ff9b:1::7f00:1"),
            ("https://six-to-four.test/oidc", "2002:7f00:1::"),
            ("https://teredo.test/oidc", "2001:0000:4136:e378:8000:63bf:3fff:fdd2"),
        ],
    )
    def test_rejects_non_public_destinations(self, public_oidc_dns, url, address):
        public_oidc_dns.return_value = [(2, 1, 6, "", (address, 443))]

        with pytest.raises(ValueError):
            validate_outbound_url(url)

    def test_rejects_credentials_and_mixed_dns(self, public_oidc_dns):
        with pytest.raises(ValueError):
            validate_outbound_url("https://user:password@idp.test/oidc")

        public_oidc_dns.return_value = [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("10.0.0.1", 443)),
        ]
        with pytest.raises(ValueError):
            validate_outbound_url("https://idp.test/oidc")

    def test_rejects_ipv4_mapped_private_ipv6_and_scoped_ipv6(self, public_oidc_dns):
        public_oidc_dns.return_value = [(10, 1, 6, "", ("::ffff:127.0.0.1", 443, 0, 0))]
        with pytest.raises(ValueError):
            validate_outbound_url("https://idp.test/oidc")

        with pytest.raises(ValueError):
            validate_outbound_url("https://[fe80::1%25eth0]/oidc")

    def test_supports_public_ipv6(self, public_oidc_dns):
        public_oidc_dns.return_value = [(10, 1, 6, "", ("2606:4700:4700::1111", 443, 0, 0))]

        target = validate_outbound_url("https://idp.test/oidc")

        assert str(target.addresses[0].ip) == "2606:4700:4700::1111"

    def test_pins_validated_address_without_second_dns_lookup(self, public_oidc_dns, mocker):
        target = validate_outbound_url("https://idp.test/oidc")
        public_oidc_dns.return_value = [(2, 1, 6, "", ("127.0.0.1", 443))]
        raw_socket = Mock()
        raw_socket.getpeername.return_value = ("8.8.8.8", 443)
        mocker.patch("plane.ext.auth.provider.oidc.socket.socket", return_value=raw_socket)
        tls_context = mocker.patch("plane.ext.auth.provider.oidc.ssl.create_default_context").return_value
        tls_context.wrap_socket.return_value = raw_socket

        connected = _connect_pinned(target, target.addresses[0], 10)

        assert connected is raw_socket
        raw_socket.connect.assert_called_once_with(("8.8.8.8", 443))
        assert tls_context.minimum_version == ssl.TLSVersion.TLSv1_3
        assert tls_context.maximum_version == ssl.TLSVersion.TLSv1_3
        tls_context.wrap_socket.assert_called_once_with(raw_socket, server_hostname="idp.test")
        assert public_oidc_dns.call_count == 1

    def test_rejects_unexpected_connected_peer(self, public_oidc_dns, mocker):
        target = validate_outbound_url("https://idp.test/oidc")
        raw_socket = Mock()
        raw_socket.getpeername.return_value = ("1.1.1.1", 80)
        mocker.patch("plane.ext.auth.provider.oidc.socket.socket", return_value=raw_socket)

        with pytest.raises(OSError):
            _connect_pinned(target, target.addresses[0], 10)

        raw_socket.close.assert_called_once()

    @override_settings(DEBUG=False)
    def test_requires_https_outside_development(self):
        with pytest.raises(ValueError):
            validate_outbound_url("http://idp.test/oidc")

    @pytest.mark.parametrize("location", ["http://10.0.0.1/internal", "https://public.example/elsewhere"])
    def test_rejects_redirects(self, location):
        response = Mock(status_code=302, headers={"Location": location})

        with pytest.raises(requests.RequestException):
            _checked_response(response)


@pytest.mark.contract
class TestOIDCInitiate:
    @pytest.mark.django_db
    def test_not_configured(self, django_client, setup_instance):
        response = django_client.get(reverse("oidc-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]

    @pytest.mark.django_db
    def test_disabled_provider_is_rejected(self, django_client, setup_instance, oidc_config):
        InstanceConfiguration.objects.update_or_create(
            key="IS_OIDC_ENABLED",
            defaults={"value": "0", "category": "OIDC", "is_encrypted": False},
        )
        response = django_client.get(reverse("oidc-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]

    @pytest.mark.django_db
    def test_rate_limit_is_enforced(self, django_client, setup_instance, oidc_config):
        with patch(
            "plane.ext.auth.views.oidc.authentication_throttle_allows",
            return_value=False,
        ):
            response = django_client.get(reverse("oidc-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"]

    @pytest.mark.django_db
    def test_https_issuer_rejects_downgraded_endpoint(self, django_client, setup_instance, oidc_config):
        cache.set(
            f"ext:oidc:discovery:{ISSUER}",
            {**DISCOVERY, "token_endpoint": "http://idp.test/token"},
            60,
        )
        response = django_client.get(reverse("oidc-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]

    @pytest.mark.django_db
    def test_redirects_to_idp_with_pkce_and_nonce(self, django_client, setup_instance, oidc_config):
        state, nonce, response = initiate(django_client)
        location = urlparse(response["Location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == DISCOVERY["authorization_endpoint"]
        query = parse_qs(location.query)
        assert query["client_id"] == [CLIENT_ID]
        assert query["response_type"] == ["code"]
        assert query["state"] == [state]
        assert query["nonce"] == [nonce]
        assert query["code_challenge_method"] == ["S256"]
        assert query["code_challenge"][0]
        assert "openid" in query["scope"][0]
        assert django_client.session[SESSION_VERIFIER]

    @pytest.mark.django_db
    def test_preserves_discovery_authorization_query(self, django_client, setup_instance, oidc_config):
        cache.set(
            f"ext:oidc:discovery:{ISSUER}",
            {**DISCOVERY, "authorization_endpoint": f"{ISSUER}/authorize?tenant=hangar"},
            60,
        )
        _, _, response = initiate(django_client)
        query = parse_qs(urlparse(response["Location"]).query)
        assert query["tenant"] == ["hangar"]
        assert query["client_id"] == [CLIENT_ID]

    @pytest.mark.django_db
    def test_app_and_space_flows_keep_separate_state(self, django_client, setup_instance, oidc_config):
        app_state, _, _ = initiate(django_client)
        space_response = django_client.get(reverse("oidc-space-initiate"))
        assert space_response.status_code == 302
        assert django_client.session[SESSION_STATE] == app_state
        assert django_client.session[f"{SESSION_STATE}_space"] != app_state


@pytest.mark.contract
class TestOIDCCallback:
    @pytest.mark.django_db
    def test_happy_path_signs_up_user(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key())
        assert response.status_code == 302
        assert error_code_of(response) is None
        user = User.objects.get(email="oidc-user@hangar.test")
        assert user.first_name == "Otto"
        assert user.last_login_medium == "oidc"
        assert django_client.session.get("_auth_user_id") == str(user.id)

    @pytest.mark.django_db
    def test_unbound_identity_cannot_claim_existing_user(self, django_client, setup_instance, oidc_config):
        existing = User.objects.create(email="oidc-user@hangar.test")
        response = run_callback(django_client, rsa_key=self._key())
        assert error_code_of(response) == AUTHENTICATION_ERROR_CODES["SSO_ACCOUNT_LINK_REQUIRED"]
        assert django_client.session.get("_auth_user_id") is None
        assert User.objects.filter(email=existing.email).count() == 1

    @pytest.mark.django_db
    def test_legacy_provider_binding_resolves_before_email(self, django_client, setup_instance, oidc_config):
        bound = User.objects.create(email="original@hangar.test", username="original")
        provider_id = hashlib.sha256(f"{ISSUER}\0user-123".encode()).hexdigest()
        Account.objects.create(
            user=bound,
            provider="oidc",
            provider_account_id=provider_id,
            access_token="legacy-token",
        )

        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides={"email": "oidc-user@hangar.test"},
        )

        assert error_code_of(response) is None
        assert django_client.session.get("_auth_user_id") == str(bound.id)

    @pytest.mark.django_db
    def test_state_mismatch_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), state="forged-state")
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_missing_code_rejected(self, django_client, setup_instance, oidc_config):
        session_state, _, _ = initiate(django_client)
        response = django_client.get(reverse("oidc-callback"), {"state": session_state, "code": ""})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]

    @pytest.mark.django_db
    def test_missing_access_token_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_response_overrides={"access_token": None},
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]

    @pytest.mark.django_db
    def test_malformed_token_response_rejected(self, django_client, setup_instance, oidc_config):
        session_state, _, _ = initiate(django_client)
        token_http_response = OIDCResponse(200, b"[]")
        with patch(
            "plane.ext.auth.provider.oidc._request_oidc",
            return_value=token_http_response,
        ) as token_post:
            response = django_client.get(
                reverse("oidc-callback"),
                {"code": "auth-code", "state": session_state},
            )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]
        assert token_post.call_args.args[0] == "POST"

    @pytest.mark.django_db
    def test_wrong_nonce_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"nonce": "evil-nonce"})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_wrong_audience_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"aud": "other-client"})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_single_audience_mismatched_azp_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides={"aud": CLIENT_ID, "azp": "other-client"},
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "token_overrides",
        [
            {"aud": CLIENT_ID},
            {"aud": CLIENT_ID, "azp": CLIENT_ID},
            {"aud": [CLIENT_ID, "resource-api"], "azp": CLIENT_ID},
        ],
    )
    def test_valid_authorized_party_combinations_accepted(
        self, django_client, setup_instance, oidc_config, token_overrides
    ):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides=token_overrides,
        )
        assert error_code_of(response) is None

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "token_overrides",
        [
            {"aud": [CLIENT_ID, "resource-api"]},
            {"aud": [CLIENT_ID, "resource-api"], "azp": "other-client"},
        ],
    )
    def test_multiple_audiences_require_matching_azp(self, django_client, setup_instance, oidc_config, token_overrides):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides=token_overrides,
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_wrong_issuer_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"iss": "https://evil.test"})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_expired_token_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides={"exp": int(time.time()) - 600, "iat": int(time.time()) - 900},
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_tampered_signature_rejected(self, django_client, setup_instance, oidc_config):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        session_state, nonce, _ = initiate(django_client)
        id_token = make_id_token(other_key, nonce=nonce)
        token_response = {"access_token": "at", "expires_in": 3600, "id_token": id_token}
        fake_jwk_client = SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=self._key().public_key())
        )
        with (
            patch(
                "plane.ext.auth.provider.oidc.OIDCOAuthProvider.get_user_token",
                return_value=token_response,
            ),
            patch("plane.ext.auth.provider.oidc._get_jwk_client", return_value=fake_jwk_client),
        ):
            response = django_client.get(reverse("oidc-callback"), {"code": "auth-code", "state": session_state})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_unverified_email_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"email_verified": False})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_UNVERIFIED_EMAIL"]
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_unverified_email_setting_cannot_override_rejection(self, django_client, setup_instance, oidc_config):
        InstanceConfiguration.objects.update_or_create(
            key="OIDC_ALLOW_UNVERIFIED_EMAIL",
            defaults={"value": "1", "category": "OIDC", "is_encrypted": False},
        )
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"email_verified": False})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_UNVERIFIED_EMAIL"]
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_id_token_and_userinfo_email_mismatch_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides={"email": "victim@hangar.test", "email_verified": None},
            userinfo_response={
                "sub": "user-123",
                "email": "attacker@hangar.test",
                "email_verified": True,
            },
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]
        assert not User.objects.filter(email__in=["victim@hangar.test", "attacker@hangar.test"]).exists()

    @pytest.mark.django_db
    def test_userinfo_email_and_verification_are_used_as_pair(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client,
            rsa_key=self._key(),
            token_overrides={"email": None, "email_verified": True},
            userinfo_response={
                "sub": "user-123",
                "email": "userinfo@hangar.test",
                "email_verified": False,
            },
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_UNVERIFIED_EMAIL"]
        assert not User.objects.filter(email="userinfo@hangar.test").exists()

    @pytest.mark.django_db
    def test_signup_disabled_without_invite_rejected(self, django_client, setup_instance, oidc_config):
        InstanceConfiguration.objects.update_or_create(
            key="ENABLE_SIGNUP", defaults={"value": "0", "category": "AUTHENTICATION", "is_encrypted": False}
        )
        response = run_callback(django_client, rsa_key=self._key())
        assert response.status_code == 302
        assert error_code_of(response) is not None
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_replayed_callback_rejected(self, django_client, setup_instance, oidc_config):
        """The session's state is single-use: a second identical callback fails."""
        first = run_callback(django_client, rsa_key=self._key())
        assert error_code_of(first) is None
        # Session state/nonce/verifier were popped — replaying the same URL
        # (fresh initiate never happened) must be rejected.
        response = django_client.get(reverse("oidc-callback"), {"code": "auth-code", "state": "stale"})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]

    @pytest.mark.django_db
    def test_open_redirect_neutralized(self, django_client, setup_instance, oidc_config):
        """A hostile absolute next_path must not produce an off-host redirect."""
        django_client.get(reverse("oidc-initiate"), {"next_path": "https://evil.test/phish"})
        state = django_client.session[SESSION_STATE]
        nonce = django_client.session[SESSION_NONCE]
        id_token = make_id_token(self._key(), nonce=nonce)
        token_response = {"access_token": "at", "expires_in": 3600, "id_token": id_token}
        fake_jwk_client = SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=self._key().public_key())
        )
        with (
            patch(
                "plane.ext.auth.provider.oidc.OIDCOAuthProvider.get_user_token",
                return_value=token_response,
            ),
            patch("plane.ext.auth.provider.oidc._get_jwk_client", return_value=fake_jwk_client),
        ):
            response = django_client.get(reverse("oidc-callback"), {"code": "c", "state": state})
        assert response.status_code == 302
        assert urlparse(response["Location"]).netloc != "evil.test"

    @staticmethod
    def _key():
        return get_rsa_key()
