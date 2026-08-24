# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What happens to accounts that already exist when a domain is pinned to Google.

An instance that pins corp.com to Google has two kinds of pre-existing account
at that domain, and they behave differently. One migrates silently on the next
sign-in; the other is locked out until an operator links it. Getting this wrong
during an upgrade locks real people out of their own workspace, so both paths
are pinned here.
"""

import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from django.urls import reverse

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.db.models import Account, FederatedIdentity, User, Workspace, WorkspaceMember
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.contract.app.test_google_auth import CLIENT_ID, error_code_of, get_rsa_key, initiate

# Re-exported rather than imported by name: pytest resolves fixtures from the
# module namespace, and importing them directly would have each test parameter
# shadow the imported symbol. Other auth suites define their own variants of
# these, so they deliberately stay per-module instead of moving to a conftest.
django_client = _google_auth.django_client
setup_instance = _google_auth.setup_instance
google_config = _google_auth.google_config

GOOGLE_ISSUER = "https://accounts.google.com"
SUBJECT = "google-sub-abc123"
EMAIL = "person@corp.com"


def _sign_in(client, *, email=EMAIL, subject=SUBJECT, hosted_domain="corp.com"):
    """Drive one Google callback for a given subject and email."""
    transaction, _ = initiate(client)
    now = int(time.time())
    claims = {
        "iss": GOOGLE_ISSUER,
        "aud": CLIENT_ID,
        "sub": subject,
        "iat": now,
        "exp": now + 300,
        "nonce": transaction["nonce"],
        "email": email,
        "email_verified": True,
        "given_name": "Existing",
        "family_name": "Person",
        "hd": hosted_domain,
    }
    id_token = jwt.encode(claims, get_rsa_key(), algorithm="RS256")
    fake_jwk_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=get_rsa_key().public_key())
    )

    with (
        patch(
            "plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_token",
            return_value={"access_token": "a", "expires_in": 3600, "id_token": id_token},
        ),
        patch(
            "plane.authentication.provider.oauth.google.GoogleOAuthProvider.get_user_response",
            return_value={
                "id": subject,
                "email": email,
                "given_name": "Existing",
                "family_name": "Person",
                "picture": "",
            },
        ),
        patch(
            "plane.authentication.provider.oauth.google._get_google_jwk_client",
            return_value=fake_jwk_client,
        ),
    ):
        return client.get(reverse("google-callback"), {"code": "c", "state": transaction["state"]})


def _existing_person(with_google_account):
    """A user who predates the migration, optionally having used Google before."""
    user = User.objects.create(email=EMAIL, username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(name="Corp", owner=user, slug=f"corp-{uuid.uuid4().hex[:6]}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20, is_active=True)
    if with_google_account:
        # This is what a prior Google sign-in leaves behind: provider_account_id
        # holds the raw Google `sub`.
        Account.objects.create(
            user=user,
            provider="google",
            provider_account_id=SUBJECT,
            access_token="old",
            last_connected_at="2026-01-01T00:00:00Z",
        )
    return user, workspace


@pytest.mark.contract
@pytest.mark.django_db
def test_account_that_already_used_google_migrates_silently(django_client, setup_instance, google_config):
    """No operator action needed: the existing Google account is adopted.

    The user keeps their id and memberships, and gains a federated identity
    bound to the same subject.
    """
    user, workspace = _existing_person(with_google_account=True)

    response = _sign_in(django_client)

    assert error_code_of(response) is None
    assert django_client.session.get("_auth_user_id") == str(user.id)
    identity = FederatedIdentity.objects.get(user=user)
    assert (identity.provider, identity.issuer, identity.subject) == ("google", GOOGLE_ISSUER, SUBJECT)
    assert WorkspaceMember.objects.filter(workspace=workspace, member=user, is_active=True).exists()
    assert User.objects.filter(email=EMAIL).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_password_only_account_is_refused_until_it_is_linked(django_client, setup_instance, google_config):
    """The case that locks people out during an upgrade.

    A person who only ever used a password or magic link has no Google account
    record to adopt, so the address is already taken by an unlinked user and
    sign-in is refused rather than silently taking the account over.
    """
    user, _workspace = _existing_person(with_google_account=False)

    response = _sign_in(django_client)

    assert error_code_of(response) == AUTHENTICATION_ERROR_CODES["SSO_ACCOUNT_LINK_REQUIRED"]
    assert django_client.session.get("_auth_user_id") is None
    assert not FederatedIdentity.objects.filter(user=user).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_importing_the_subject_unblocks_that_account(django_client, setup_instance, google_config):
    """The supported remedy: bind the subject ahead of the first sign-in.

    This is what import_federated_identities writes, and it is why the Google
    `sub` has to be collected before the cutover.
    """
    user, workspace = _existing_person(with_google_account=False)
    FederatedIdentity.objects.create(
        user=user,
        provider="google",
        issuer=GOOGLE_ISSUER,
        subject=SUBJECT,
        subject_format="",
        email_at_link=EMAIL,
        last_email=EMAIL,
    )

    response = _sign_in(django_client)

    assert error_code_of(response) is None
    assert django_client.session.get("_auth_user_id") == str(user.id)
    assert WorkspaceMember.objects.filter(workspace=workspace, member=user, is_active=True).exists()
    assert User.objects.filter(email=EMAIL).count() == 1
