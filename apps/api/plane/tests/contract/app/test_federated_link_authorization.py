# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Linking an existing account to an asserted identity, by address.

Sign-in refuses to link an account by email, because an address proves nothing:
whoever controls a mailbox — or a provider willing to assert any address — would
otherwise take over accounts. An authorization relaxes that for one address,
once, and every test here is about a condition that keeps the relaxation narrow.

The one that matters most is domain pinning. Without it, an operator who
authorised `person@gmail.com` would be trusting whoever answers for gmail.com;
with it, the identity provider is the authority for the domain, which is the
whole basis for accepting an address as identification.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import FederatedIdentity, User
from plane.ext.models import FederatedLinkAudit, FederatedLinkAuthorization
from plane.ext.services.federated_link import claim_authorization
from plane.license.models import InstanceAdmin, InstanceConfiguration
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin

setup_instance = _google_auth.setup_instance

URL = "/api/instances/identity-import/link-authorizations/"
ISSUER = "https://accounts.google.com"
PASSWORD = "correct-horse-battery-staple-42"


def _user(email, password=None):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    if password:
        user.set_password(password)
        user.save()
    return user


def _pin(value="corp.com=google"):
    InstanceConfiguration.objects.update_or_create(
        key="SSO_ENFORCED_DOMAINS",
        defaults={"value": value, "category": "SSO", "is_encrypted": False},
    )


def _authorize(email, provider="google", issuer=ISSUER, expires_in=timedelta(days=7), actor=None):
    return FederatedLinkAuthorization.objects.create(
        email=email,
        provider=provider,
        issuer=issuer,
        authorized_by=actor,
        expires_at=timezone.now() + expires_in,
    )


@pytest.fixture
def admin_client(db, setup_instance):
    admin = _user("admin@ops.example", PASSWORD)
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    return client


@pytest.mark.contract
@pytest.mark.django_db
def test_an_authorised_address_in_a_pinned_domain_is_linked(db):
    _pin()
    person = _user("person@corp.com")
    _authorize("person@corp.com")

    claimed = claim_authorization(
        email="person@corp.com", provider="google", issuer=ISSUER, subject="sub-1", user=person
    )

    assert claimed is not None
    assert claimed.consumed_subject == "sub-1"
    record = FederatedLinkAudit.objects.get(email="person@corp.com")
    assert record.subject == "sub-1"
    assert record.user_id == person.id


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unpinned_domain_is_refused_however_it_was_authorised(db):
    """The condition the whole relaxation rests on.

    Without a pinned domain, an address says only that somebody typed it.
    """
    _pin("other.com=google")
    person = _user("person@gmail.com")
    _authorize("person@gmail.com")

    assert (
        claim_authorization(email="person@gmail.com", provider="google", issuer=ISSUER, subject="sub-1", user=person)
        is None
    )
    assert not FederatedLinkAudit.objects.exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_different_provider_cannot_spend_it(db):
    _pin("corp.com=google;saml")
    person = _user("person@corp.com")
    _authorize("person@corp.com", provider="google")

    assert (
        claim_authorization(
            email="person@corp.com", provider="saml", issuer="https://idp.example", subject="s", user=person
        )
        is None
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_it_can_only_be_spent_once(db):
    _pin()
    person = _user("person@corp.com")
    _authorize("person@corp.com")

    first = claim_authorization(email="person@corp.com", provider="google", issuer=ISSUER, subject="sub-1", user=person)
    FederatedIdentity.objects.filter(user=person).delete()
    second = claim_authorization(
        email="person@corp.com", provider="google", issuer=ISSUER, subject="sub-2", user=person
    )

    assert first is not None
    assert second is None


@pytest.mark.contract
@pytest.mark.django_db
def test_an_expired_authorisation_is_not_spendable(db):
    """A list nobody acted on stops being a way in."""
    _pin()
    person = _user("person@corp.com")
    _authorize("person@corp.com", expires_in=timedelta(days=-1))

    assert (
        claim_authorization(email="person@corp.com", provider="google", issuer=ISSUER, subject="s", user=person) is None
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_an_account_that_already_signs_in_this_way_is_left_alone(db):
    """A second identity at one issuer is another way into the account."""
    _pin()
    person = _user("person@corp.com")
    FederatedIdentity.objects.create(
        user=person,
        provider="google",
        issuer=ISSUER,
        subject="existing",
        subject_format="",
        email_at_link=person.email,
        last_email=person.email,
    )
    _authorize("person@corp.com")

    assert (
        claim_authorization(email="person@corp.com", provider="google", issuer=ISSUER, subject="new", user=person)
        is None
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_the_record_of_a_link_cannot_be_altered(db):
    _pin()
    person = _user("person@corp.com")
    _authorize("person@corp.com")
    claim_authorization(email="person@corp.com", provider="google", issuer=ISSUER, subject="s", user=person)

    record = FederatedLinkAudit.objects.get()
    record.note = "something else"
    with pytest.raises(Exception):
        record.save()
    with pytest.raises(Exception):
        record.delete()


@pytest.mark.contract
@pytest.mark.django_db
def test_only_an_administrator_with_the_second_factor_reaches_the_endpoint(db, setup_instance):
    ordinary = APIClient()
    ordinary.force_authenticate(user=_user("nobody@corp.com"))
    assert ordinary.get(URL).status_code in (401, 403)
    assert APIClient().get(URL).status_code in (401, 403)

    admin = _user("admin2@ops.example", PASSWORD)
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    without_factor = APIClient()
    without_factor.force_authenticate(user=admin)
    assert without_factor.get(URL).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_the_preview_says_what_each_address_will_do_and_writes_nothing(admin_client):
    _pin()
    _user("person@corp.com")
    _user("outside@other.com")

    response = admin_client.post(
        URL,
        {"provider": "google", "issuer": ISSUER, "emails": "person@corp.com\noutside@other.com\nghost@corp.com"},
        format="json",
    )

    states = {row["email"]: row["state"] for row in response.data["rows"]}
    assert states["person@corp.com"] == "will-link"
    assert states["outside@other.com"] == "domain-not-pinned"
    assert states["ghost@corp.com"] == "no-account"
    assert not FederatedLinkAuthorization.objects.exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_confirming_takes_the_password_and_authorises_only_the_linkable(admin_client):
    _pin()
    _user("person@corp.com")

    refused = admin_client.post(
        URL,
        {"provider": "google", "issuer": ISSUER, "emails": "person@corp.com", "confirm": "true"},
        format="json",
    )
    assert refused.status_code == 403
    assert not FederatedLinkAuthorization.objects.exists()

    accepted = admin_client.post(
        URL,
        {
            "provider": "google",
            "issuer": ISSUER,
            "emails": "person@corp.com\nghost@corp.com",
            "confirm": "true",
            "password": PASSWORD,
        },
        format="json",
    )

    assert accepted.status_code == 200
    assert accepted.data["authorized"] == 1
    assert list(FederatedLinkAuthorization.objects.values_list("email", flat=True)) == ["person@corp.com"]


@pytest.mark.contract
@pytest.mark.django_db
def test_something_that_is_not_an_address_is_named_rather_than_ignored(admin_client):
    response = admin_client.post(
        URL, {"provider": "google", "issuer": ISSUER, "emails": "person@corp.com\nnot-an-address"}, format="json"
    )

    assert response.status_code == 400
    assert "not-an-address" in response.data["error"]
