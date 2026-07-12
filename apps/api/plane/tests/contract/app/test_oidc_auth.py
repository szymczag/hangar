# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import time
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch
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
):
    """Drive the callback with a canned token response signed by rsa_key."""
    session_state, nonce, _ = initiate(django_client)
    overrides = {"nonce": nonce}
    overrides.update(token_overrides or {})
    id_token = make_id_token(rsa_key, **overrides)
    token_response = {"access_token": "at-123", "expires_in": 3600, "id_token": id_token}
    token_response.update(token_response_overrides or {})

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
    def test_https_issuer_rejects_downgraded_endpoint(
        self, django_client, setup_instance, oidc_config
    ):
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
    def test_preserves_discovery_authorization_query(
        self, django_client, setup_instance, oidc_config
    ):
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
    def test_app_and_space_flows_keep_separate_state(
        self, django_client, setup_instance, oidc_config
    ):
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
        token_http_response = Mock()
        token_http_response.raise_for_status.return_value = None
        token_http_response.json.return_value = []
        with patch(
            "plane.ext.auth.provider.oidc.requests.post",
            return_value=token_http_response,
        ) as token_post:
            response = django_client.get(
                reverse("oidc-callback"),
                {"code": "auth-code", "state": session_state},
            )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"]
        assert token_post.call_args.kwargs["timeout"] == 10

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
