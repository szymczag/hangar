# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The instance user listing reports accounts; it must not expose or manage them.

It exists so an operator can see who has an account and how they sign in before
pinning a domain. Two properties matter beyond the listing itself: only an
instance administrator may read it, and it offers no way to change anything.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import Account, FederatedIdentity, User
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth

setup_instance = _google_auth.setup_instance

URL = "/api/instances/users/"


def _user(email, *, password=False, active=True, bot=False):
    return User.objects.create(
        email=email,
        username=uuid.uuid4().hex,
        is_password_autoset=not password,
        is_active=active,
        is_bot=bot,
    )


def _bind(user, provider="google", issuer="https://accounts.google.com"):
    return FederatedIdentity.objects.create(
        user=user,
        provider=provider,
        issuer=issuer,
        subject=uuid.uuid4().hex,
        subject_format="",
        email_at_link=user.email,
        last_email=user.email,
    )


def _oauth(user, provider="google"):
    return Account.objects.create(
        user=user,
        provider=provider,
        provider_account_id=uuid.uuid4().hex,
        access_token="t",
        last_connected_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def admin_client(db, setup_instance):
    admin = _user("admin@ops.example", password=True)
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def plain_client(db):
    client = APIClient()
    client.force_authenticate(user=_user("nobody@corp.com", password=True))
    return client


def _emails(response):
    return {row["email"] for row in response.data["results"]}


def _row(response, email):
    return next(row for row in response.data["results"] if row["email"] == email)


@pytest.mark.contract
@pytest.mark.django_db
def test_requires_instance_administrator(plain_client):
    """An ordinary account must not enumerate everyone on the instance."""
    assert plain_client.get(URL).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_anonymous_access_is_refused(db):
    assert APIClient().get(URL).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_reports_how_each_account_signs_in(admin_client):
    bound = _user("bound@corp.com")
    _bind(bound)
    adoptable = _user("adoptable@corp.com")
    _oauth(adoptable)
    _user("passwordonly@corp.com", password=True)

    response = admin_client.get(URL, {"domain": "corp.com", "provider": "google"})

    assert response.status_code == 200
    assert _row(response, "bound@corp.com")["status"] == "federated"
    assert _row(response, "adoptable@corp.com")["status"] == "adoptable"
    assert _row(response, "passwordonly@corp.com")["status"] == "needs-import"
    assert _row(response, "bound@corp.com")["federated_identities"][0]["provider"] == "google"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_binding_to_another_provider_still_needs_an_import(admin_client):
    """The case most easily mistaken for safe."""
    user = _user("saml@corp.com")
    _bind(user, provider="saml", issuer="https://idp.example")

    response = admin_client.get(URL, {"domain": "corp.com", "provider": "google"})

    assert _row(response, "saml@corp.com")["status"] == "needs-import"


@pytest.mark.contract
@pytest.mark.django_db
def test_filters_by_domain_and_search(admin_client):
    _user("person@corp.com", password=True)
    _user("person@other.com", password=True)

    assert _emails(admin_client.get(URL, {"domain": "corp.com"})) == {"person@corp.com"}
    assert "person@other.com" in _emails(admin_client.get(URL, {"search": "other"}))


@pytest.mark.contract
@pytest.mark.django_db
def test_deactivated_and_bot_accounts_are_hidden_by_default(admin_client):
    _user("gone@corp.com", active=False)
    _user("bot@corp.com", bot=True)

    default = _emails(admin_client.get(URL, {"domain": "corp.com"}))
    assert "gone@corp.com" not in default
    assert "bot@corp.com" not in default

    with_inactive = _emails(admin_client.get(URL, {"domain": "corp.com", "include_inactive": "true"}))
    assert "gone@corp.com" in with_inactive
    # Bots act only through API tokens and are never sign-in accounts, so they
    # stay out regardless.
    assert "bot@corp.com" not in with_inactive


@pytest.mark.contract
@pytest.mark.django_db
def test_unknown_provider_is_rejected_rather_than_ignored(admin_client):
    """Silently ignoring it would report every account as needing an import."""
    assert admin_client.get(URL, {"provider": "nonsense"}).status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_listing_is_read_only(admin_client):
    for method in (admin_client.post, admin_client.patch, admin_client.delete, admin_client.put):
        assert method(URL, {}, format="json").status_code == 405


@pytest.mark.contract
@pytest.mark.django_db
def test_never_exposes_credential_material(admin_client):
    user = _user("person@corp.com", password=True)
    user.set_password("correct-horse-battery-staple-42")
    user.save()
    _oauth(user)

    response = admin_client.get(URL, {"domain": "corp.com"})
    row = _row(response, "person@corp.com")

    assert "password" not in row
    assert "access_token" not in str(row)
    assert row["has_password"] is True
