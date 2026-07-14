# Copyright (c) 2026-present Maciej Szymczak and contributors
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
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.authentication.views.app.google import GOOGLE_TRANSACTION_APP
from plane.authentication.views.space.google import GOOGLE_TRANSACTION_SPACE
from plane.db.models import FederatedIdentity, User
from plane.license.models import Instance, InstanceConfiguration

CLIENT_ID = "google-client"
_RSA_KEY = None


def get_rsa_key():
    global _RSA_KEY
    if _RSA_KEY is None:
        _RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return _RSA_KEY


@pytest.fixture
def setup_instance(db):
    instance_id = uuid.uuid4() if not Instance.objects.exists() else Instance.objects.first().id
    return Instance.objects.update_or_create(
        id=instance_id,
        defaults={
            "instance_name": "Test Instance",
            "instance_id": str(uuid.uuid4()),
            "current_version": "1.0.0",
            "domain": "http://localhost:8000",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )[0]


@pytest.fixture
def google_config(db):
    for key, value in (
        ("IS_GOOGLE_ENABLED", "1"),
        ("GOOGLE_CLIENT_ID", CLIENT_ID),
        ("GOOGLE_CLIENT_SECRET", "google-secret"),
        ("GOOGLE_AUTH_MODE", "generic"),
        ("GOOGLE_WORKSPACE_DOMAINS", ""),
        ("ENABLE_SIGNUP", "1"),
    ):
        InstanceConfiguration.objects.update_or_create(
            key=key,
            defaults={"value": value, "category": "GOOGLE", "is_encrypted": False},
        )


@pytest.fixture
def django_client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 test-client")


def error_code_of(response):
    query = parse_qs(urlparse(response["Location"]).query)
    return int(query["error_code"][0]) if "error_code" in query else None


def initiate(client, *, space=False):
    response = client.get(reverse("space-google-initiate" if space else "google-initiate"))
    assert response.status_code == 302
    transaction_key = GOOGLE_TRANSACTION_SPACE if space else GOOGLE_TRANSACTION_APP
    return client.session[transaction_key], response


def run_callback(client, *, space=False, token_overrides=None, userinfo_overrides=None):
    transaction, _ = initiate(client, space=space)
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-user-123",
        "iat": now,
        "exp": now + 300,
        "nonce": transaction["nonce"],
        "email": "google-user@hangar.test",
        "email_verified": True,
        "given_name": "Grace",
        "family_name": "Workspace",
    }
    claims.update(token_overrides or {})
    id_token = jwt.encode(claims, get_rsa_key(), algorithm="RS256")
    token_response = {"access_token": "google-access", "expires_in": 3600, "id_token": id_token}
    userinfo = {
        "id": claims["sub"],
        "email": claims["email"],
        "given_name": claims.get("given_name"),
        "family_name": claims.get("family_name"),
        "picture": "",
    }
    userinfo.update(userinfo_overrides or {})
    fake_jwk_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=get_rsa_key().public_key())
    )

    with (
        patch(
            "plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_token",
            return_value=token_response,
        ),
        patch(
            "plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_response",
            return_value=userinfo,
        ),
        patch(
            "plane.authentication.provider.oauth.google._get_google_jwk_client",
            return_value=fake_jwk_client,
        ),
    ):
        return client.get(
            reverse("space-google-callback" if space else "google-callback"),
            {"code": "google-code", "state": transaction["state"]},
        )


@pytest.mark.contract
class TestGoogleAuthentication:
    @pytest.mark.django_db
    def test_callback_without_pending_state_is_rejected_before_exchange(
        self, django_client, setup_instance, google_config
    ):
        with patch("plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_token") as token_exchange:
            response = django_client.get(reverse("google-callback"), {"code": "attacker-code", "state": ""})

        assert error_code_of(response) == AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"]
        token_exchange.assert_not_called()

    @pytest.mark.django_db
    def test_valid_flow_uses_pkce_nonce_and_persists_identity(self, django_client, setup_instance, google_config):
        transaction, response = initiate(django_client)
        query = parse_qs(urlparse(response["Location"]).query)
        assert query["nonce"] == [transaction["nonce"]]
        assert query["code_challenge_method"] == ["S256"]
        assert query["redirect_uri"] == ["http://testserver/auth/google/callback/"]

        now = int(time.time())
        id_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": CLIENT_ID,
                "sub": "google-user-123",
                "iat": now,
                "exp": now + 300,
                "nonce": transaction["nonce"],
                "email": "google-user@hangar.test",
                "email_verified": True,
            },
            get_rsa_key(),
            algorithm="RS256",
        )
        fake_jwk_client = SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=get_rsa_key().public_key())
        )
        with (
            patch(
                "plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_token",
                return_value={"access_token": "at", "expires_in": 3600, "id_token": id_token},
            ),
            patch(
                "plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_response",
                return_value={"id": "google-user-123", "email": "google-user@hangar.test"},
            ),
            patch(
                "plane.authentication.provider.oauth.google._get_google_jwk_client",
                return_value=fake_jwk_client,
            ),
        ):
            callback = django_client.get(
                reverse("google-callback"),
                {"code": "code", "state": transaction["state"]},
            )

        assert error_code_of(callback) is None
        user = User.objects.get(email="google-user@hangar.test")
        identity = FederatedIdentity.objects.get(user=user)
        assert identity.issuer == "https://accounts.google.com"
        assert identity.subject == "google-user-123"

    @pytest.mark.django_db
    def test_state_is_one_shot(self, django_client, setup_instance, google_config):
        transaction, _ = initiate(django_client)
        first = django_client.get(reverse("google-callback"), {"code": "", "state": transaction["state"]})
        second = django_client.get(reverse("google-callback"), {"code": "bad", "state": transaction["state"]})
        assert first.status_code == 302
        assert error_code_of(second) == AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"]

    @pytest.mark.django_db
    def test_disabled_provider_blocks_initiation_and_in_flight_callback(
        self, django_client, setup_instance, google_config
    ):
        transaction, _ = initiate(django_client)
        InstanceConfiguration.objects.filter(key="IS_GOOGLE_ENABLED").update(value="0")
        response = django_client.get(
            reverse("google-callback"),
            {"code": "code", "state": transaction["state"]},
        )
        assert error_code_of(response) == AUTHENTICATION_ERROR_CODES["GOOGLE_NOT_CONFIGURED"]

        second_client = Client()
        initiate_response = second_client.get(reverse("google-initiate"))
        assert error_code_of(initiate_response) == AUTHENTICATION_ERROR_CODES["GOOGLE_NOT_CONFIGURED"]

    @pytest.mark.django_db
    def test_workspace_mode_enforces_signed_hosted_domain(self, django_client, setup_instance, google_config):
        InstanceConfiguration.objects.filter(key="GOOGLE_AUTH_MODE").update(value="workspace")
        InstanceConfiguration.objects.filter(key="GOOGLE_WORKSPACE_DOMAINS").update(value="example.com")

        rejected = run_callback(django_client, token_overrides={"hd": "other.example"})
        assert error_code_of(rejected) == AUTHENTICATION_ERROR_CODES["GOOGLE_WORKSPACE_TENANT_NOT_ALLOWED"]

        accepted = run_callback(django_client, token_overrides={"hd": "example.com"})
        assert error_code_of(accepted) is None

    @pytest.mark.django_db
    def test_app_and_space_transactions_and_redirect_uris_are_separate(
        self, django_client, setup_instance, google_config
    ):
        app_transaction, app_response = initiate(django_client)
        space_transaction, space_response = initiate(django_client, space=True)

        assert app_transaction["state"] != space_transaction["state"]
        assert django_client.session[GOOGLE_TRANSACTION_APP]["state"] == app_transaction["state"]
        assert django_client.session[GOOGLE_TRANSACTION_SPACE]["state"] == space_transaction["state"]
        assert parse_qs(urlparse(app_response["Location"]).query)["redirect_uri"] == [
            "http://testserver/auth/google/callback/"
        ]
        assert parse_qs(urlparse(space_response["Location"]).query)["redirect_uri"] == [
            "http://testserver/auth/spaces/google/callback/"
        ]

    @pytest.mark.django_db
    def test_bound_subject_cannot_switch_to_existing_email(self, django_client, setup_instance, google_config):
        first = run_callback(django_client)
        assert error_code_of(first) is None
        bound = User.objects.get(email="google-user@hangar.test")
        victim = User.objects.create(email="victim@hangar.test", username="victim")

        second = run_callback(
            django_client,
            token_overrides={"email": victim.email},
            userinfo_overrides={"email": victim.email},
        )

        assert error_code_of(second) is None
        assert django_client.session.get("_auth_user_id") == str(bound.id)
