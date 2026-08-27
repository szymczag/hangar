# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An account that signs in through a provider does not own its own address.

The federated binding is a digest over provider, issuer, subject format and
subject. Email takes no part in it, so changing the address does not break
sign-in — and that is exactly why it must be refused rather than left alone. The
address is what domain policy reads: `SSO_ENFORCED_DOMAINS` pins a domain to a
provider, and auto-join grants workspaces by domain. Proving control of some
other mailbox would otherwise let an account keep its identity while moving out
from under the policy that admitted it, or into one that would admit it to more.

Both the request for a verification code and the change itself are checked,
because either alone would leave a way through.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import FederatedIdentity, Profile, User

ISSUER = "https://accounts.google.com"
GENERATE_URL = "/api/users/me/email/generate-code/"
UPDATE_URL = "/api/users/me/email/"


def _account(email, federated):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    if federated:
        FederatedIdentity.objects.create(
            user=user,
            provider="google",
            issuer=ISSUER,
            subject=uuid.uuid4().hex,
            subject_format="",
            email_at_link=email,
            last_email=email,
        )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_is_refused_a_new_address():
    client, user = _account("person@corp.com", federated=True)

    response = client.patch(UPDATE_URL, {"email": "person@elsewhere.test", "code": "123456"}, format="json")

    assert response.status_code == 403
    assert "identity provider" in response.data["error"]
    user.refresh_from_db()
    assert user.email == "person@corp.com"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_cannot_even_start_the_change():
    """Refusing only at the end would still send a code to the other mailbox."""
    client, _ = _account("person@corp.com", federated=True)

    response = client.post(GENERATE_URL, {"email": "person@elsewhere.test"}, format="json")

    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_an_account_with_a_password_is_left_alone():
    """The refusal is about federation, not about changing an address at all."""
    client, _ = _account("person@corp.com", federated=False)

    response = client.post(GENERATE_URL, {"email": "person@elsewhere.test"}, format="json")

    assert response.status_code != 403


@pytest.mark.contract
@pytest.mark.django_db
def test_the_account_reports_that_it_is_federated():
    """The application has to know, or it goes on offering what will be refused."""
    federated, _ = _account("person@corp.com", federated=True)
    ordinary, _ = _account("other@corp.com", federated=False)

    assert federated.get("/api/users/me/").data["is_federated"] is True
    assert ordinary.get("/api/users/me/").data["is_federated"] is False
