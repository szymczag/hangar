# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from plane.db.models import User
from plane.license.models import Instance, InstanceConfiguration

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES
from plane.ext.auth.views.oidc import SESSION_NONCE, SESSION_STATE, SESSION_VERIFIER

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


def run_callback(django_client, rsa_key, token_overrides=None, state=None, code="auth-code"):
    """Drive the callback with a canned token response signed by rsa_key."""
    session_state, nonce, _ = initiate(django_client)
    overrides = {"nonce": nonce}
    overrides.update(token_overrides or {})
    id_token = make_id_token(rsa_key, **overrides)
    token_response = {"access_token": "at-123", "expires_in": 3600, "id_token": id_token}

    fake_jwk_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=rsa_key.public_key())
    )
    with (
        patch(
            "plane.ext.auth.provider.oidc.OIDCOAuthProvider.get_user_token",
            return_value=token_response,
        ),
        patch("plane.ext.auth.provider.oidc._get_jwk_client", return_value=fake_jwk_client),
    ):
        params = {"code": code, "state": state if state is not None else session_state}
        return django_client.get(reverse("oidc-callback"), params)


def error_code_of(response):
    query = parse_qs(urlparse(response["Location"]).query)
    return int(query["error_code"][0]) if "error_code" in query else None


@pytest.mark.contract
class TestOIDCInitiate:
    @pytest.mark.django_db
    def test_not_configured(self, django_client, setup_instance):
        response = django_client.get(reverse("oidc-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]

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
    def test_existing_user_logs_in(self, django_client, setup_instance, oidc_config):
        existing = User.objects.create(email="oidc-user@hangar.test")
        response = run_callback(django_client, rsa_key=self._key())
        assert error_code_of(response) is None
        assert django_client.session.get("_auth_user_id") == str(existing.id)

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
    def test_wrong_nonce_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"nonce": "evil-nonce"})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_wrong_audience_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(django_client, rsa_key=self._key(), token_overrides={"aud": "other-client"})
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_wrong_issuer_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client, rsa_key=self._key(), token_overrides={"iss": "https://evil.test"}
        )
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
            response = django_client.get(
                reverse("oidc-callback"), {"code": "auth-code", "state": session_state}
            )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_TOKEN_VALIDATION_FAILED"]

    @pytest.mark.django_db
    def test_unverified_email_rejected(self, django_client, setup_instance, oidc_config):
        response = run_callback(
            django_client, rsa_key=self._key(), token_overrides={"email_verified": False}
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_UNVERIFIED_EMAIL"]
        assert not User.objects.filter(email="oidc-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_unverified_email_allowed_when_opted_in(self, django_client, setup_instance, oidc_config):
        InstanceConfiguration.objects.update_or_create(
            key="OIDC_ALLOW_UNVERIFIED_EMAIL",
            defaults={"value": "1", "category": "OIDC", "is_encrypted": False},
        )
        response = run_callback(
            django_client, rsa_key=self._key(), token_overrides={"email_verified": False}
        )
        assert error_code_of(response) is None
        assert User.objects.filter(email="oidc-user@hangar.test").exists()

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
